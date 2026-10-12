"""Procedural graph semantics, seamless geometry and the native brush consumer."""
import base64
import copy
import ctypes
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPointF,QRectF
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtSvg import QSvgRenderer
from modules.texture_creator import engine
from modules.texture_creator.interface import TextureCreator

ROOT=Path(__file__).resolve().parents[1]


class TextureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_every_preset_is_deterministic_geometry(self):
        for name in engine.PRESETS:
            with self.subTest(name=name):
                graph=engine.preset(name)
                self.assertEqual(engine.png_bytes(engine.render(graph,128)),engine.png_bytes(engine.render(graph,128)))
                vector=engine.svg(graph)
                self.assertIn('<path',vector);self.assertNotIn('<image',vector);self.assertNotIn('base64',vector)
                self.assertTrue(QSvgRenderer(vector.encode()).isValid())

    def test_seed_changes_distribution_without_external_images(self):
        graph=engine.preset('Terrazzo');before=engine.png_bytes(engine.render(graph,128))
        graph['nodes'][1]['params']['seed']+=1
        self.assertNotEqual(before,engine.png_bytes(engine.render(graph,128)))
        self.assertFalse(any('file' in p or 'path' in p for n in graph['nodes'] for p in n['params']))

    def test_partial_shape_wraps_to_opposite_edge(self):
        nodes=[engine.make_node('Shape',0),engine.make_node('Output',1)]
        nodes[0]['params'].update(x=0,y=256,size=100)
        graph={'nodes':nodes,'edges':[{'from':'n0','to':'n1'}],'settings':{'seamless':True,'background':'transparent'}}
        image=engine.render(graph,512)
        self.assertGreater(image.pixelColor(5,256).alpha(),240)
        self.assertGreater(image.pixelColor(507,256).alpha(),240)
        graph['settings']['seamless']=False
        image=engine.render(graph,512)
        self.assertEqual(image.pixelColor(507,256).alpha(),0)

    def test_svg_matches_raster_at_sample_points(self):
        graph=engine.preset('Halftone');raster=engine.render(graph,256)
        vector=QImage(256,256,QImage.Format.Format_ARGB32_Premultiplied);vector.fill(0)
        painter=QPainter(vector);QSvgRenderer(engine.svg(graph).encode()).render(painter);painter.end()
        for y in range(8,250,16):
            for x in range(8,250,16):
                a,b=raster.pixelColor(x,y),vector.pixelColor(x,y)
                self.assertLessEqual(max(abs(a.getRgb()[i]-b.getRgb()[i]) for i in range(4)),3)

    def test_cycles_missing_inputs_and_shape_budget_are_rejected(self):
        graph=engine.preset();graph['edges'].append({'from':'n2','to':'n1','input':0})
        with self.assertRaises(ValueError):engine.evaluate(graph)
        graph=engine.preset();graph['edges']=[]
        with self.assertRaisesRegex(ValueError,'Connect'):engine.evaluate(graph)
        graph=engine.preset('Halftone');node=engine.make_node('Grid',9);node['params'].update(columns=80,rows=80)
        graph['nodes'].append(node);graph['edges']=[{'from':'n0','to':'n1'},{'from':'n1','to':'n9'},{'from':'n9','to':'n2'},{'from':'n2','to':'n3'}]
        with self.assertRaisesRegex(ValueError,'instances'):engine.evaluate(graph)

    def test_boolean_subtract_preserves_hole(self):
        a,b,operation,out=[engine.make_node(k,i) for i,k in enumerate(['Shape','Shape','Boolean','Output'])]
        a['params']['size']=300;b['params']['size']=100
        graph={'nodes':[a,b,operation,out],'edges':[{'from':'n0','to':'n2'},{'from':'n1','to':'n2','input':1},{'from':'n2','to':'n3'}],'settings':{'background':'transparent','seamless':False}}
        image=engine.render(graph,512,mask=True)
        self.assertEqual(image.pixelColor(256,256).alpha(),0)
        self.assertGreater(image.pixelColor(350,256).alpha(),240)

    def test_tip_and_grain_are_distinct_native_payloads(self):
        graph=engine.preset('Organic stamp')
        tip=engine.brush_payload(graph,size=128)
        grain=engine.brush_payload(graph,size=128,role='grain')
        self.assertIn('_csbr_bitmap_tip_png',tip)
        self.assertNotIn('_csbr_bitmap_tip_png',grain)
        image=QImage.fromData(base64.b64decode(grain['_csbr_texture_png']))
        self.assertEqual(image.pixelColor(0,0).alpha(),255)
        self.assertLess(image.pixelColor(0,0).red(),5)
        self.assertGreater(image.pixelColor(64,64).red(),240)

    def test_graph_roundtrip_and_future_version(self):
        graph=engine.preset('Cellular stone')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'stone.cstx';engine.save_graph(graph,path)
            self.assertEqual(engine.load_graph(path),graph)
        graph['version']=99
        with self.assertRaisesRegex(ValueError,'version'):engine.evaluate(graph)

    def test_interface_history_and_async_latest_result(self):
        creator=TextureCreator({});widget=creator.edit_widget();widget.resize(1000,700);widget.show()
        try:
            creator.set_parameter('n1','count',50)
            creator.set_parameter('n1','count',70)
            creator.undo();self.assertEqual(creator.graph['nodes'][1]['params']['count'],50)
            creator.redo();self.assertEqual(creator.graph['nodes'][1]['params']['count'],70)
            deadline=time.monotonic()+5
            while (creator.image.isNull() or creator._busy or creator._timer.isActive()) and time.monotonic()<deadline:
                self.app.processEvents();time.sleep(.02)
            self.assertFalse(creator.image.isNull())
            self.assertIn('70 paths',creator.status.text())
            self.assertFalse(creator.connect_nodes('n2','n1',0))
        finally:creator.shutdown();widget.close();widget.deleteLater();self.app.processEvents()

    def test_native_brush_renders_generated_tip_and_grain(self):
        import sys
        sys.path.insert(0,str(ROOT/'Nebula'))
        from CORE.native_bridge import load_creative_core
        lib=load_creative_core()
        self.assertIsNotNone(lib,'CreativeCore must be built for this integration test')
        graph=engine.preset('Organic stamp');tip=base64.b64decode(engine.brush_payload(graph,size=128)['_csbr_bitmap_tip_png'])
        brush=lib.cs_brush_create()
        try:
            data=(ctypes.c_uint8*len(tip)).from_buffer_copy(tip)
            self.assertEqual(lib.cs_brush_set_bitmap_tip_png(brush,data,len(tip)),1)
            lib.cs_brush_set_size(brush,ctypes.c_float(70))
            lib.cs_brush_set_color(brush,40,170,100,255)
            pixels=(ctypes.c_uint8*(128*128*4))()
            lib.cs_brush_draw_segment(brush,pixels,128,128,512,ctypes.c_float(40),ctypes.c_float(64),ctypes.c_float(88),ctypes.c_float(64),ctypes.c_float(1),ctypes.c_float(1))
            self.assertGreater(sum(pixels[3::4]),10000)
            with tempfile.TemporaryDirectory() as directory:
                file=Path(directory)/'grain.png';file.write_bytes(base64.b64decode(engine.brush_payload(graph,size=128,role='grain')['_csbr_texture_png']))
                self.assertEqual(lib.cs_brush_set_texture_path(brush,str(file).encode()),1)
        finally:lib.cs_brush_destroy(brush)



class FieldGraphTests(unittest.TestCase):
    """Continuous fields, typed ports and field-driven geometry."""
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_material_presets_are_valid_seamless_vectors(self):
        for name in engine.MATERIALS:
            with self.subTest(name=name):
                graph=engine.preset(name);graph['settings']['field_resolution']=128
                vector=engine.svg(graph)
                self.assertIn('<path',vector);self.assertNotIn('<image',vector)
                self.assertTrue(QSvgRenderer(vector.encode()).isValid())
                image=engine.render(graph,128)
                # Seamless: opposite edges agree as well as neighbouring columns do.
                edge=sum(abs(image.pixelColor(0,y).value()-image.pixelColor(127,y).value()) for y in range(128))
                inner=sum(abs(image.pixelColor(63,y).value()-image.pixelColor(64,y).value()) for y in range(128))
                self.assertLess(edge,max(400,inner*3))

    def test_contour_bands_are_not_wrapped_twice(self):
        graph=engine.preset('Woven fabric');graph['settings']['field_resolution']=128
        shapes=engine.evaluate(graph)
        self.assertTrue(all(s.tiled for s in shapes))
        self.assertEqual(len(engine.wrapped(shapes,True)),len(shapes))

    def test_field_cannot_feed_a_geometry_input(self):
        graph=engine.preset('Terrazzo');perlin=engine.make_node('Perlin',9)
        graph['nodes'].append(perlin);graph['edges'][0]={'from':perlin['id'],'to':graph['nodes'][1]['id'],'input':0}
        with self.assertRaisesRegex(ValueError,'expects geometry'):engine.validate(graph)

    def test_output_accepts_a_field_directly(self):
        nodes=[engine.make_node('Perlin',0),engine.make_node('Output',1)]
        graph={'version':1,'nodes':nodes,'edges':[{'from':'n0','to':'n1','input':0}],'settings':{'field_resolution':64}}
        shapes=engine.evaluate(graph);self.assertGreater(len(shapes),3)

    def _geometry_with_field(self,kind,**params):
        nodes=[engine.make_node('Grid',1),engine.make_node('Shape',0),engine.make_node('Gradient',2),engine.make_node(kind,3),engine.make_node('Output',4)]
        nodes[3]['params'].update(params)
        edges=[{'from':'n0','to':'n1','input':0},{'from':'n1','to':'n3','input':0},{'from':'n2','to':'n3','input':1},{'from':'n3','to':'n4','input':0}]
        return {'version':1,'nodes':nodes,'edges':edges,'settings':{'field_resolution':64,'seamless':False}}

    def test_mask_by_field_drives_opacity_and_culling(self):
        shapes=engine.evaluate(self._geometry_with_field('Mask by field',mode='opacity'))
        self.assertGreater(max(s.opacity for s in shapes)-min(s.opacity for s in shapes),.5)
        culled=engine.evaluate(self._geometry_with_field('Mask by field',mode='cull',threshold=.5))
        self.assertLess(len(culled),len(shapes))

    def test_displace_by_field_moves_paths(self):
        still=engine.evaluate(self._geometry_with_field('Displace by field',amount=0))
        moved=engine.evaluate(self._geometry_with_field('Displace by field',amount=40))
        self.assertNotEqual(still[0].path.boundingRect(),moved[0].path.boundingRect())

    def test_flow_scatter_follows_density(self):
        shapes=engine.evaluate(self._geometry_with_field('Flow scatter',count=150,density=3))  # 64 grid shapes x 150 < 12,000 budget
        xs=[s.path.boundingRect().center().x() for s in shapes]
        self.assertGreater(sum(x>256 for x in xs),sum(x<256 for x in xs))  # linear gradient is brighter on the right

    def test_field_preview_thumbnail(self):
        graph=engine.preset('Leather');graph['settings']['field_resolution']=64
        image=engine.field_preview(graph,graph['nodes'][0]['id'],48)
        self.assertEqual((image.width(),image.height()),(48,48))
        self.assertIsNone(engine.field_preview(graph,graph['nodes'][-1]['id']))



class TextureV3Tests(unittest.TestCase):
    """Brush masks from fields, colour ramps, relief, colour by field, height/normal maps."""
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def small(self,name):
        graph=engine.preset(name);graph['settings']['field_resolution']=96;return graph

    def test_field_brush_is_greyscale_not_a_white_square(self):
        payload=engine.brush_payload(self.small('Leather'),'leather',64,'tip')
        mask=QImage.fromData(base64.b64decode(payload['_csbr_bitmap_tip_png']))
        alphas={mask.pixelColor(x,y).alpha() for x in range(0,64,4) for y in range(0,64,4)}
        self.assertGreater(len(alphas),8)
        grain=engine.brush_payload(self.small('Woven fabric'),'fabric',64,'grain')
        image=QImage.fromData(base64.b64decode(grain['_csbr_texture_png']))
        values={image.pixelColor(x,y).value() for x in range(0,64,4) for y in range(0,64,4)}
        self.assertGreater(len(values),8)

    def test_contour_mask_render_encodes_levels(self):
        image=engine.render(self.small('Marble'),64,mask=True)
        alphas={image.pixelColor(x,y).alpha() for x in range(64) for y in range(64)}
        self.assertGreater(len(alphas),6)

    def test_three_colour_ramp_reaches_the_mid_colour(self):
        p={'ramp':'3 colours','color_low':'#000000','color_mid':'#ff0000','color_high':'#ffffff','mid_position':.5}
        self.assertEqual(engine._ramp_color(p,.5),'#ff0000')
        self.assertEqual(engine._ramp_color({**p,'ramp':'2 colours'},.5),'#808080')

    def test_relief_node_and_color_by_field(self):
        nodes=[engine.make_node('Shape',0),engine.make_node('Grid',1),engine.make_node('Gradient',2),
               engine.make_node('Relief',3),engine.make_node('Color by field',4),engine.make_node('Output',5)]
        nodes[4]['params'].update(ramp='2 colours',color_low='#000000',color_high='#ffffff')
        edges=[{'from':'n0','to':'n1','input':0},{'from':'n2','to':'n3','input':0},{'from':'n1','to':'n4','input':0},
               {'from':'n2','to':'n4','input':1},{'from':'n4','to':'n5','input':0}]
        shapes=engine.evaluate({'version':1,'nodes':nodes,'edges':edges,'settings':{'field_resolution':64}})
        self.assertGreater(len({s.color for s in shapes}),4)
        self.assertEqual(engine.field_preview({'version':1,'nodes':nodes,'edges':edges,'settings':{'field_resolution':64}},'n3',32).width(),32)

    def test_height_and_normal_maps(self):
        graph=self.small('Cracked earth')
        height=engine.height_image(graph,64);normal=engine.normal_image(graph,64)
        self.assertEqual(height.format(),QImage.Format.Format_Grayscale16)
        self.assertEqual((normal.width(),normal.height()),(64,64))
        self.assertGreater(sum(normal.pixelColor(x,32).blue() for x in range(64))/64,180)  # mostly facing the viewer
        with self.assertRaisesRegex(ValueError,'field-based'):engine.height_image(engine.preset('Terrazzo'),64)



class TextureV4Tests(unittest.TestCase):
    """Groups, cache, thumbnails, smooth raster, PBR, rasterize, image input, editor tools."""
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def small(self,name):
        graph=engine.preset(name);graph['settings']['field_resolution']=96;return graph

    def test_new_material_presets_render(self):
        for name in ('Hex tiles','Fish scales','Pebble path','Bevelled bricks'):
            with self.subTest(name=name):
                graph=self.small(name);self.assertIn('<path',engine.svg(graph))
                self.assertFalse(engine.render(graph,64).isNull())

    def test_group_renders_exactly_like_its_nodes(self):
        graph=self.small('Leather');ids=[n['id'] for n in graph['nodes'][:5]]
        grouped,gid=engine.group_nodes(graph,ids,'Leather base')
        self.assertEqual(engine.png_bytes(engine.render(graph,64)),engine.png_bytes(engine.render(grouped,64)))
        restored,_=engine.ungroup(grouped,gid)
        self.assertEqual(engine.png_bytes(engine.render(graph,64)),engine.png_bytes(engine.render(restored,64)))

    def test_thumbnails_and_errors_for_every_node(self):
        graph=self.small('Hex tiles');graph['nodes'].append(engine.make_node('Blend',40))
        values,errors=engine.all_values(graph)
        self.assertIn('n40',errors)  # unconnected Blend reports, others still render
        for nid,value in values.items():
            self.assertFalse(engine.thumbnail(value,32).isNull())

    def test_cache_returns_identical_values(self):
        graph=self.small('Marble');first=engine.evaluate(graph);second=engine.evaluate(graph)
        self.assertIs(first,second)

    def test_smooth_raster_is_continuous(self):
        nodes=[engine.make_node('Gradient',0),engine.make_node('Contours',1),engine.make_node('Output',2)]
        nodes[1]['params'].update(levels=4)
        graph={'version':1,'nodes':nodes,'edges':[{'from':'n0','to':'n1','input':0},{'from':'n1','to':'n2','input':0}],
               'settings':{'field_resolution':128,'seamless':False}}
        row=lambda img:len({img.pixelColor(x,48).rgb() for x in range(96)})
        banded=engine.render(graph,96)
        graph['settings']['smooth']=True;smooth=engine.render(graph,96)
        self.assertLessEqual(row(banded),12)   # 4 bands (+ antialiased edges)
        self.assertGreaterEqual(row(smooth),60)  # a new shade almost every pixel

    def test_pbr_maps(self):
        maps=engine.pbr_maps(self.small('Bevelled bricks'),64)
        self.assertEqual(set(maps),{'basecolor','height','normal','ao','roughness','metallic'})
        self.assertEqual(maps['height'].format(),QImage.Format.Format_Grayscale16)
        self.assertEqual(maps['roughness'].pixelColor(5,5).value(),round(.8*255))  # Output roughness parameter

    def test_rasterize_turns_geometry_into_a_field(self):
        graph=self.small('Bevelled bricks');values,_=engine.all_values(graph)
        field=values[graph['nodes'][1]['id']]
        self.assertGreater(float(field.max()),.9);self.assertLess(float(field.min()),.1)

    def test_image_node_reads_a_picture(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ramp.png';image=QImage(64,32,QImage.Format.Format_RGB32)
            for x in range(64):
                for y in range(32):image.setPixelColor(x,y,QColor(x*4,x*4,x*4))
            image.save(str(path))
            nodes=[engine.make_node('Image',0),engine.make_node('Output',1)]
            nodes[0]['params'].update(path=str(path),tileable='no')
            graph={'version':1,'nodes':nodes,'edges':[{'from':'n0','to':'n1','input':0}],'settings':{'field_resolution':64}}
            field,_=engine.output_field(graph)
            self.assertLess(float(field[:,2].mean()),.1);self.assertGreater(float(field[:,-3].mean()),.85)
            nodes[0]['params']['path']=str(Path(folder)/'missing.png')
            with self.assertRaisesRegex(ValueError,'cannot read'):engine.evaluate(graph)

    def test_editor_duplicate_expose_and_search(self):
        creator=TextureCreator({});creator.edit_widget()
        before=len(creator.graph['nodes']);first=creator.graph['nodes'][0]['id']
        creator.scene.nodes[first].setSelected(True);creator.duplicate_selected()
        self.assertEqual(len(creator.graph['nodes']),before+1)
        key=next(iter(engine.SCHEMA[creator.graph['nodes'][0]['type']]['params']))
        creator.toggle_expose(first,key)
        self.assertEqual(creator.quick_form.rowCount(),1)
        creator.node_choice.setEditText('pebb');creator.add_node()
        self.assertEqual(creator.graph['nodes'][-1]['type'],'Pebbles')
        creator.shutdown()


if __name__=='__main__':unittest.main()
