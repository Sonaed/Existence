"""Deterministic geometry graphs. No image input, SVG embeds no raster content.

Geometry is in a 512-unit tile. Raster resolution is independent of geometry.
All effects retain paths; seamless output wraps complete paths on a torus.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import math
import os
import random
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPainterPathStroker, QTransform

TILE=512.0
MAX_SHAPES=12000
MAX_NODES=128

# key: label, kind, default, minimum, maximum (or choices)
def number(label,default,lo,hi): return (label,'number',default,lo,hi)
def choice(label,default,values): return (label,'choice',default,values)
def color(label,default): return (label,'color',default)
SCHEMA={
 'Noise':dict(category='Generators',inputs=0,params={
     'cells':number('Vector resolution',64,8,96),'frequency':number('Frequency',4,1,24),
     'octaves':number('Octaves',3,1,5),'persistence':number('Persistence',.5,.05,.95),
     'contrast':number('Contrast',1.5,.1,6),'bias':number('Bias',0,-1,1),'threshold':number('Cutoff',0,0,.95),
     'seed':number('Seed',42,0,1000000)}),
 'Shape':dict(category='Generators',inputs=0,params={
     'shape':choice('Primitive','ellipse',['ellipse','rectangle','polygon','star','ring','blob']),
     'size':number('Width',100,1,1024),'aspect':number('Aspect',1,.02,8),'sides':number('Sides / lobes',6,3,64),
     'inner':number('Inner radius',.5,.02,.98),'roundness':number('Corner radius',12,0,256),
     'roughness':number('Organic variation',.25,0,.9),'seed':number('Seed',17,0,1000000),
     'x':number('Center X',256,-512,1024),'y':number('Center Y',256,-512,1024)}),
 'Scatter':dict(category='Distribution',inputs=1,params={
     'count':number('Count',160,1,3000),'seed':number('Seed',42,0,1000000),
     'min_scale':number('Minimum scale',.05,.001,4),'max_scale':number('Maximum scale',.22,.001,4),
     'rotation':number('Rotation range',180,0,360),'opacity_min':number('Minimum opacity',.35,0,1),
     'distribution':choice('Distribution','uniform',['uniform','cluster','radial']),
     'spread':number('Cluster spread',.24,.01,1),'radius':number('Radial radius',190,0,512)}),
 'Grid':dict(category='Distribution',inputs=1,params={
     'columns':number('Columns',8,1,80),'rows':number('Rows',8,1,80),'scale':number('Scale',.3,.001,4),
     'offset':number('Alternate row offset',.5,0,1),'jitter':number('Position jitter',0,0,1),
     'rotation':number('Rotation',0,-180,180),'seed':number('Seed',12,0,1000000)}),
 'Waves':dict(category='Generators',inputs=0,params={
     'count':number('Lines',20,1,200),'amplitude':number('Amplitude',12,0,180),
     'frequency':number('Cycles',3,1,30),'phase':number('Phase',0,0,1),'drift':number('Line phase drift',.06,0,1),
     'width':number('Line width',3,.2,80),'angle':number('Angle',0,-180,180),'seed':number('Seed',7,0,1000000),
     'irregularity':number('Irregularity',.1,0,1)}),
 'Bricks':dict(category='Generators',inputs=0,params={
     'columns':number('Columns',6,1,50),'rows':number('Rows',10,1,50),'gap':number('Mortar',4,0,80),
     'offset':number('Bond offset',.5,0,1),'roundness':number('Corner radius',3,0,40),
     'jitter':number('Edge variation',.06,0,.5),'seed':number('Seed',31,0,1000000)}),
 'Voronoi':dict(category='Generators',inputs=0,params={
     'count':number('Cells',45,3,140),'gap':number('Cell gap',3,0,30),'seed':number('Seed',17,0,1000000)}),
 'Transform':dict(category='Geometry',inputs=1,params={
     'scale_x':number('Scale X',1,.01,6),'scale_y':number('Scale Y',1,.01,6),
     'angle':number('Rotation',0,-180,180),'x':number('Offset X',0,-1024,1024),'y':number('Offset Y',0,-1024,1024)}),
 'Mirror':dict(category='Geometry',inputs=1,params={'axis':choice('Axis','horizontal',['horizontal','vertical','both'])}),
 'Radial':dict(category='Distribution',inputs=1,params={'count':number('Copies',8,1,128),
     'radius':number('Radius',150,0,700),'start':number('Start angle',0,-180,180),
     'scale':number('Scale',.4,.01,4),'rotate':choice('Orient copies','yes',['yes','no'])}),
 'Warp':dict(category='Geometry',inputs=1,params={'amount':number('Displacement',10,0,100),
     'frequency':number('Period count',3,1,24),'seed':number('Seed',12,0,1000000),'detail':number('Path detail',4,1,16)}),
 'Outline':dict(category='Geometry',inputs=1,params={'width':number('Outline width',3,.1,100)}),
 'Boolean':dict(category='Composition',inputs=2,params={'operation':choice('Operation','subtract',['union','subtract','intersect','xor'])}),
 'Merge':dict(category='Composition',inputs=2,params={}),
 'Colorize':dict(category='Appearance',inputs=1,params={'color':color('Ink','#c7b391'),
     'second':color('Variation colour','#f6ead2'),'variation':number('Colour variation',.3,0,1),
     'opacity':number('Opacity',1,0,1),'seed':number('Seed',9,0,1000000)}),
 'Output':dict(category='Output',inputs=4,ports=('any','field','field','field'),optional=(1,2,3),
     port_names=('Colour','Height','Roughness','Metallic'),params={
     'roughness':number('Roughness (if unconnected)',.6,0,1),'metallic':number('Metallic (if unconnected)',0,0,1),
     'normal_depth':number('Normal depth',4,0,40),'ao_radius':number('AO radius',16,2,64)}),
 # ── Continuous fields (values 0–1 over the tile, seamless) ──
 'Perlin':dict(category='Field generators',inputs=0,out='field',params={
     'frequency':number('Frequency',4,1,32),'octaves':number('Octaves',5,1,8),'persistence':number('Persistence',.5,.05,1),
     'lacunarity':number('Lacunarity',2,2,4),'mode':choice('Mode','fbm',['fbm','turbulence','ridged']),
     'stretch':number('Stretch (streaks)',1,1,16),'seed':number('Seed',42,0,1000000)}),
 'Fibers':dict(category='Field generators',inputs=0,out='field',params={
     'count':number('Fibres',700,10,6000),'length':number('Length',90,4,400),'thickness':number('Thickness',1.2,.3,12),
     'angle':number('Direction',0,-180,180),'spread':number('Direction spread',40,0,180),'curl':number('Curl',.4,0,1),
     'seed':number('Seed',3,0,1000000)}),
 'Cracks':dict(category='Field generators',inputs=0,out='field',params={
     'mode':choice('Pattern','cracks',['cracks','cells','crackle']),'count':number('Cells',40,3,300),
     'width':number('Crack width',2.5,.2,30),'jitter':number('Irregularity',1,0,1),'warp':number('Organic warp',.5,0,3),
     'seed':number('Seed',5,0,1000000)}),
 'Veins':dict(category='Field generators',inputs=0,out='field',params={
     'kind':choice('Material','wood',['wood','marble','grain']),'rings':number('Rings / veins',12,1,80),
     'distortion':number('Distortion',1,0,4),'detail':number('Detail',4,1,16),'sharpness':number('Sharpness',2,.2,10),
     'direction':choice('Direction','horizontal',['horizontal','vertical']),'seed':number('Seed',8,0,1000000)}),
 'Weave':dict(category='Field generators',inputs=0,out='field',params={
     'pattern':choice('Weave','plain',['plain','twill','basket','satin']),'threads':number('Threads',16,2,96),
     'width':number('Thread width',.82,.2,1),'roundness':number('Roundness',.6,0,1),'variation':number('Thread variation',.25,0,1),
     'seed':number('Seed',1,0,1000000)}),
 'Gradient':dict(category='Field generators',inputs=0,out='field',params={
     'kind':choice('Shape','linear',['linear','radial','diamond','triangle']),'angle':number('Angle',0,-180,180),
     'repeat':number('Repeat',1,1,16)}),
 'Levels':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'low':number('Input black',0,0,1),'high':number('Input white',1,0,1),'gamma':number('Gamma',1,.1,5),
     'contrast':number('Contrast',1,.1,8),'steps':number('Posterize steps (0 = off)',0,0,32),'invert':choice('Invert','no',['no','yes'])}),
 'Blend':dict(category='Field operations',inputs=3,ports=('field','field','field'),optional=(2,),port_names=('A','B','Mask'),
     out='field',params={'mode':choice('Blend mode','multiply',['mix','multiply','screen','overlay','soft light','add',
     'subtract','difference','lighten','darken','height max']),'opacity':number('Opacity',1,0,1)}),
 'Field warp':dict(category='Field operations',inputs=2,ports=('field','field'),port_names=('Source','Displacement'),out='field',params={
     'mode':choice('Displace','value',['value','gradient','direction']),'amount':number('Amount',24,0,256),
     'angle':number('Angle',0,-180,180),'turns':number('Direction turns',1,0,8)}),
 'Multiscale':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'scales':number('Scales',3,1,5),'falloff':number('Falloff',.5,.1,1),'mode':choice('Combine','add',['add','max'])}),
 'Blur':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'radius':number('Radius',4,0,64),'angle':number('Direction',0,-180,180),'stretch':number('Directional stretch',1,1,16)}),
 'Erosion':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'strength':number('Strength',.6,0,1),'iterations':number('Iterations',6,1,20),'angle':number('Gravity direction',90,-180,180),
     'streak':number('Streak length',24,1,128),'seed':number('Seed',4,0,1000000)}),
 'Relief':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'angle':number('Light direction',-135,-180,180),'elevation':number('Light elevation',45,1,90),
     'depth':number('Depth',4,0,40),'mix':number('Shading amount',1,0,1)}),
 'Wear':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'amount':number('Wear amount',.5,0,1),'edge_width':number('Edge width',6,1,64),'breakup':number('Breakup',.6,0,1),
     'seed':number('Seed',6,0,1000000)}),
 'Tiles':dict(category='Field generators',inputs=0,out='field',params={
     'pattern':choice('Pattern','brick',['brick','grid','hex']),'columns':number('Columns',6,1,64),'rows':number('Rows',12,1,64),
     'gap':number('Mortar gap',4,0,64),'bevel':number('Bevel width',6,0,64),'profile':choice('Bevel profile','round',['round','linear','flat']),
     'variation':number('Height variation',.25,0,1),'seed':number('Seed',7,0,1000000)}),
 'Scales':dict(category='Field generators',inputs=0,out='field',params={
     'columns':number('Columns',8,2,48),'rows':number('Rows',14,2,64),'overlap':number('Overlap',.5,0,1),
     'roundness':number('Roundness',.8,0,1),'variation':number('Tone variation',.2,0,1),'seed':number('Seed',3,0,1000000)}),
 'Pebbles':dict(category='Field generators',inputs=0,out='field',params={
     'count':number('Stones',60,3,300),'gap':number('Gap',.15,0,.8),'roundness':number('Roundness',.7,0,1),
     'variation':number('Surface variation',.35,0,1),'jitter':number('Irregularity',.8,0,1),'seed':number('Seed',2,0,1000000)}),
 'Stripes':dict(category='Field generators',inputs=0,out='field',params={
     'count':number('Stripes',8,1,64),'angle':number('Angle',0,-180,180),'sharpness':number('Sharpness',1,.05,10),
     'wobble':number('Wobble',0,0,4),'seed':number('Seed',1,0,1000000)}),
 'Image':dict(category='Field generators',inputs=0,out='field',params={
     'path':('Image file','file',''),'channel':choice('Channel','luminance',['luminance','red','green','blue','alpha']),
     'tileable':choice('Make tileable','yes',['yes','no']),'blend':number('Seam blend',.15,.02,.5),'invert':choice('Invert','no',['no','yes'])}),
 'Bevel':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'threshold':number('Shape threshold',.5,0,1),'width':number('Bevel width',8,1,64),
     'profile':choice('Profile','round',['round','linear','flat']),'keep_height':number('Keep source height',0,0,1)}),
 'Slope blur':dict(category='Field operations',inputs=2,ports=('field','field'),port_names=('Source','Slope'),out='field',params={
     'amount':number('Amount',12,0,128),'samples':number('Samples',8,2,24)}),
 'Histogram scan':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'position':number('Position',.5,0,1),'contrast':number('Contrast',.5,0,1)}),
 'Symmetry':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'mode':choice('Symmetry','mirror x',['mirror x','mirror y','mirror xy','4 segments','6 segments','8 segments','12 segments'])}),
 'Slope':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={'depth':number('Depth',4,.1,40)}),
 'Curvature':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'radius':number('Radius',3,1,32),'mode':choice('Keep','convex',['convex','concave'])}),
 'Ambient occlusion':dict(category='Field operations',inputs=1,ports=('field',),out='field',params={
     'radius':number('Radius',16,2,64),'strength':number('Strength',1,0,2)}),
 'Rasterize':dict(category='Geometry → field',inputs=1,ports=('geometry',),out='field',params={
     'mode':choice('Value','coverage',['coverage','luminance']),'blur':number('Soften',0,0,32),'invert':choice('Invert','no',['no','yes'])}),
 'Group':dict(category='Groups',inputs=0,hidden=True,params={}),
 'Group input':dict(category='Groups',inputs=0,out='field',hidden=True,params={'index':number('Input index',0,0,3)}),
 # ── Bridges between fields and vector geometry ──
 'Contours':dict(category='Field → geometry',inputs=1,ports=('field',),params={
     'mode':choice('Output','bands',['bands','lines','threshold']),'levels':number('Levels',16,2,64),
     'threshold':number('Threshold',.5,0,1),'color_low':color('Low colour','#2b2118'),'color_high':color('High colour','#e9d3b0'),
     'ramp':choice('Colour ramp','2 colours',['2 colours','3 colours']),'color_mid':color('Mid colour','#8a6040'),
     'mid_position':number('Mid position',.5,.01,.99),
     'line_width':number('Line width',1,.2,20),'detail':number('Detail (grid)',192,32,512),'opacity':number('Opacity',1,0,1)}),
 'Mask by field':dict(category='Field → geometry',inputs=2,ports=('geometry','field'),port_names=('Geometry','Mask'),params={
     'mode':choice('Effect','opacity',['opacity','cull']),'threshold':number('Threshold',0,0,1),
     'contrast':number('Contrast',1,.1,8),'invert':choice('Invert','no',['no','yes'])}),
 'Displace by field':dict(category='Field → geometry',inputs=2,ports=('geometry','field'),port_names=('Geometry','Displacement'),params={
     'mode':choice('Direction','value',['value','gradient']),'amount':number('Amount',20,0,256),
     'angle':number('Angle',0,-180,180),'detail':number('Path detail',4,1,16)}),
 'Color by field':dict(category='Field → geometry',inputs=2,ports=('geometry','field'),port_names=('Geometry','Colour'),params={
     'color_low':color('Low colour','#3d2a1c'),'color_high':color('High colour','#e8cfa2'),
     'ramp':choice('Colour ramp','3 colours',['2 colours','3 colours']),'color_mid':color('Mid colour','#a0704a'),
     'mid_position':number('Mid position',.5,.01,.99),'contrast':number('Contrast',1,.1,8),'mix':number('Amount',1,0,1)}),
 'Flow scatter':dict(category='Field → geometry',inputs=2,ports=('geometry','field'),port_names=('Geometry','Density / direction'),params={
     'count':number('Count',300,1,3000),'density':number('Density contrast',1.5,.1,8),
     'align':choice('Orientation','along',['along','across','none']),'jitter':number('Rotation jitter',15,0,180),
     'min_scale':number('Minimum scale',.05,.001,4),'max_scale':number('Maximum scale',.15,.001,4),'seed':number('Seed',11,0,1000000)}),
}
for _spec in SCHEMA.values():
    _spec.setdefault('ports',('geometry',)*_spec['inputs'])
    _spec['inputs']=len(_spec['ports'])
    _spec.setdefault('out','geometry'); _spec.setdefault('optional',())
    _spec.setdefault('port_names',tuple('ABCDEFGH'[i] for i in range(_spec['inputs'])))


def output_type(kind):return SCHEMA[kind]['out']

@dataclass
class Shape:
    path: QPainterPath
    color: str='#ffffff'
    opacity: float=1.0
    tiled: bool=False  # already covers the tile periodically (contours): never re-wrapped
    level: float|None=None  # field level of a contour band: brush masks render it as grey, not white


def make_node(kind,index=0):
    return {'id':f'n{index}','type':kind,'x':80+index*240,'y':120,
            'params':{key:copy.deepcopy(value[2]) for key,value in SCHEMA[kind]['params'].items()}}


def node_spec(node):
    """Ports and output type of a node. Group / Group input nodes define them per instance."""
    kind=node['type'];spec=SCHEMA[kind]
    if kind=='Group':
        g=node.get('group') or {};ports=tuple(g.get('ports',()))
        names=tuple(g.get('port_names') or tuple(f'In {i+1}' for i in range(len(ports))))
        return {**spec,'ports':ports,'inputs':len(ports),'optional':(),'port_names':names,'out':g.get('out','geometry')}
    if kind=='Group input':return {**spec,'out':node.get('input_type','field')}
    return spec


def validate(graph,*,partial=False,_depth=0):
    if not isinstance(graph,dict):raise ValueError('Texture must be a graph object')
    if graph.get('version',1) != 1:raise ValueError('Unsupported texture graph version')
    if _depth>4:raise ValueError('Groups are nested too deeply')
    settings=graph.get('settings',{})
    if not isinstance(settings,dict):raise ValueError('Invalid texture settings')
    resolution=settings.get('resolution',1024)
    if not isinstance(resolution,int) or not 16<=resolution<=8192:raise ValueError('Resolution must be 16–8192 pixels')
    field_resolution=settings.get('field_resolution',256)
    if not isinstance(field_resolution,int) or not 64<=field_resolution<=1024:raise ValueError('Field resolution must be 64–1024')
    if not isinstance(settings.get('smooth',False),bool):raise ValueError('Invalid smooth setting')
    background=settings.get('background','#202b30')
    if background!='transparent' and not QColor(background).isValid():raise ValueError('Invalid background colour')
    exposed=graph.get('exposed',[])
    if not isinstance(exposed,list) or len(exposed)>48 or not all(isinstance(e,dict) and isinstance(e.get('node'),str)
            and isinstance(e.get('param'),str) for e in exposed):raise ValueError('Invalid exposed parameters')
    nodes=graph.get('nodes',[]);edges=graph.get('edges',[])
    if not isinstance(nodes,list) or not isinstance(edges,list) or len(edges)>256:raise ValueError('Invalid graph structure')
    if not nodes or len(nodes)>MAX_NODES:raise ValueError(f'Use 1–{MAX_NODES} nodes')
    lookup={}
    for node in nodes:
        if not isinstance(node,dict) or not isinstance(node.get('params',{}),dict):raise ValueError('Invalid node structure')
        nid=node.get('id');kind=node.get('type')
        if not isinstance(nid,str) or nid in lookup:raise ValueError('Node IDs must be unique strings')
        if kind not in SCHEMA:raise ValueError(f'Unsupported node: {kind}')
        if kind=='Group input' and _depth==0:raise ValueError('Group input nodes only exist inside groups')
        for axis in ('x','y'):
            position=node.get(axis,0)
            if not isinstance(position,(int,float)) or not math.isfinite(position) or abs(position)>1000000:raise ValueError('Invalid node position')
        lookup[nid]=node
        for key,spec in SCHEMA[kind]['params'].items():
            value=node.get('params',{}).get(key,spec[2])
            if spec[1]=='number' and (not isinstance(value,(int,float)) or not math.isfinite(value) or not spec[3]<=value<=spec[4]):
                raise ValueError(f'{kind}: {spec[0]} must be between {spec[3]} and {spec[4]}')
            if spec[1]=='choice' and value not in spec[3]:raise ValueError(f'{kind}: invalid {key}')
            if spec[1]=='color' and not QColor(value).isValid():raise ValueError(f'{kind}: invalid colour')
            if spec[1]=='file' and (not isinstance(value,str) or len(value)>4096):raise ValueError(f'{kind}: invalid file path')
        if kind=='Group':
            group=node.get('group')
            if not isinstance(group,dict) or not isinstance(group.get('graph'),dict):raise ValueError('Group without content')
            ports=group.get('ports',[])
            if not isinstance(ports,list) or len(ports)>4 or any(p not in ('field','geometry') for p in ports):raise ValueError('Invalid group inputs')
            if group.get('out') not in ('field','geometry'):raise ValueError('Invalid group output')
            ilookup,iinputs,_,iout=validate(group['graph'],partial=True,_depth=_depth+1)
            for inner in ilookup.values():
                if inner['type']=='Group input':
                    index=int(inner.get('params',{}).get('index',0))
                    if index>=len(ports) or inner.get('input_type')!=ports[index]:raise ValueError('Group inputs do not match the group ports')
            source=iinputs[iout].get(0)
            if source is None or node_spec(ilookup[source])['out']!=group['out']:raise ValueError('Group output type mismatch')
    inputs={key:{} for key in lookup}
    for edge in edges:
        if not isinstance(edge,dict):raise ValueError('Invalid connection structure')
        a,b,port=edge.get('from'),edge.get('to'),edge.get('input',0)
        if a not in lookup or b not in lookup or not isinstance(port,int) or not 0<=port<node_spec(lookup[b])['inputs']:
            raise ValueError('Invalid connection')
        if port in inputs[b]:raise ValueError('Each input accepts one connection')
        if lookup[a]['type']=='Output':raise ValueError('Output cannot feed another node')
        target=node_spec(lookup[b]);expected=target['ports'][port];given=node_spec(lookup[a])['out']
        if expected!='any' and expected!=given:
            raise ValueError(f"{lookup[b]['type']} input {target['port_names'][port]} expects {expected}; {lookup[a]['type']} gives {given}")
        inputs[b][port]=a
    outputs=[n['id'] for n in nodes if n['type']=='Output']
    if len(outputs)!=1:raise ValueError('The graph needs exactly one Output node')
    order=[];visited=set();active=set()
    def visit(nid):
        if nid in active:raise ValueError('A geometry graph cannot contain cycles')
        if nid in visited:return
        active.add(nid)
        for parent in inputs[nid].values():visit(parent)
        active.remove(nid);visited.add(nid);order.append(nid)
    for nid in lookup:visit(nid)
    if partial:return lookup,inputs,order,outputs[0]
    # Disconnected nodes can be edited without blocking the output.
    reachable=set()
    def mark(nid):
        reachable.add(nid)
        spec=node_spec(lookup[nid])
        missing=[spec['port_names'][i] for i in range(spec['inputs']) if i not in spec['optional'] and i not in inputs[nid]]
        if missing:raise ValueError(f"Connect input {', '.join(missing)} of {lookup[nid]['type']}")
        for parent in inputs[nid].values():
            if parent not in reachable:mark(parent)
    mark(outputs[0])
    return lookup,inputs,[nid for nid in order if nid in reachable],outputs[0]


def _mapped(shapes,transform):return [Shape(transform.map(s.path),s.color,s.opacity) for s in shapes]
def _around(x,y,angle=0,sx=1,sy=None):
    t=QTransform();t.translate(x,y);t.rotate(angle);t.scale(sx,sx if sy is None else sy);t.translate(-256,-256);return t


def _primitive(p):
    path=QPainterPath();w=p['size'];h=w*p['aspect'];x,y=p['x'],p['y'];kind=p['shape']
    r=QRectF(x-w/2,y-h/2,w,h)
    if kind in ('ellipse','ring'):path.addEllipse(r)
    elif kind=='rectangle':path.addRoundedRect(r,p['roundness'],p['roundness'])
    else:
        rng=random.Random(int(p['seed']));count=int(p['sides']);count*=2 if kind=='star' else 1
        for i in range(count):
            a=i*math.tau/count-math.pi/2
            radius=p['inner'] if kind=='star' and i%2 else 1
            if kind=='blob':radius*=1-rng.random()*p['roughness']
            point=QPointF(x+math.cos(a)*w*.5*radius,y+math.sin(a)*h*.5*radius)
            path.lineTo(point) if i else path.moveTo(point)
        path.closeSubpath()
    if kind=='ring':
        inner=QPainterPath();inner.addEllipse(QRectF(x-w*p['inner']/2,y-h*p['inner']/2,w*p['inner'],h*p['inner']))
        path=path.subtracted(inner)
    return [Shape(path)]


def _clip_polygon(poly,nx,ny,c):
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=a[0]*nx+a[1]*ny-c;db=b[0]*nx+b[1]*ny-c
        if da<=1e-8:out.append(a)
        if (da<0)!=(db<0):
            t=da/(da-db);out.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
    return out


def _generator(kind,p):
    rng=random.Random(int(p.get('seed',0)))
    if kind=='Shape':return _primitive(p)
    result=[]
    if kind=='Noise':
        cells=int(p['cells']);octaves=int(p['octaves']);tables=[]
        for octave in range(octaves):
            frequency=int(p['frequency'])*2**octave
            tables.append((frequency,[[rng.random() for _ in range(frequency)] for _ in range(frequency)]))
        def noise(x,y):
            total=weight=0;amplitude=1
            for frequency,table in tables:
                xx,yy=x*frequency,y*frequency;ix,iy=math.floor(xx),math.floor(yy);fx,fy=xx-ix,yy-iy
                fx=fx*fx*(3-2*fx);fy=fy*fy*(3-2*fy)
                a=table[iy%frequency][ix%frequency]*(1-fx)+table[iy%frequency][(ix+1)%frequency]*fx
                b=table[(iy+1)%frequency][ix%frequency]*(1-fx)+table[(iy+1)%frequency][(ix+1)%frequency]*fx
                total+=(a*(1-fy)+b*fy)*amplitude;weight+=amplitude;amplitude*=p['persistence']
            return max(0,min(1,(total/weight-.5)*p['contrast']+.5+p['bias']))
        for y in range(cells):
            for x in range(cells):
                value=noise((x+.5)/cells,(y+.5)/cells)
                if value<=p['threshold']:continue
                path=QPainterPath();path.addRect(QRectF(x*TILE/cells,y*TILE/cells,TILE/cells,TILE/cells))
                result.append(Shape(path,opacity=value))
        return result
    if kind=='Waves':
        count=int(p['count']);frequency=int(p['frequency'])
        for line in range(count):
            path=QPainterPath();phase=p['phase']+line*p['drift'];base=(line+.5)*TILE/count
            for i in range(257):
                x=i*TILE/256
                y=base+math.sin(math.tau*(x/TILE*frequency+phase))*p['amplitude']
                y+=math.sin(math.tau*(x/TILE*(frequency+2)+phase*2))*p['amplitude']*p['irregularity']
                path.lineTo(x,y) if i else path.moveTo(x,y)
            stroker=QPainterPathStroker();stroker.setWidth(p['width']);stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
            result.append(Shape(stroker.createStroke(path)))
        return _mapped(result,_around(256,256,p['angle']))
    if kind=='Bricks':
        cols,rows=int(p['columns']),int(p['rows']);cw,ch=TILE/cols,TILE/rows
        for row in range(rows):
            for col in range(cols):
                gap=p['gap']+rng.random()*min(cw,ch)*p['jitter'];path=QPainterPath()
                rect=QRectF((col+(row%2)*p['offset'])*cw+gap/2,row*ch+gap/2,max(.1,cw-gap),max(.1,ch-gap))
                path.addRoundedRect(rect,p['roundness'],p['roundness']);result.append(Shape(path))
        return result
    if kind=='Voronoi':
        points=[(rng.random()*TILE,rng.random()*TILE) for _ in range(int(p['count']))]
        # Neighbours in the eight adjacent tiles yield periodic cells.
        neighbours=[(x+dx*TILE,y+dy*TILE) for dx in (-1,0,1) for dy in (-1,0,1) for x,y in points]
        for x,y in points:
            poly=[(x-TILE,y-TILE),(x+TILE,y-TILE),(x+TILE,y+TILE),(x-TILE,y+TILE)]
            for xx,yy in neighbours:
                if xx==x and yy==y:continue
                poly=_clip_polygon(poly,xx-x,yy-y,(xx*xx+yy*yy-x*x-y*y)/2)
                if not poly:break
            if not poly:continue
            path=QPainterPath();path.moveTo(*poly[0])
            for vertex in poly[1:]:path.lineTo(*vertex)
            path.closeSubpath()
            if p['gap']:
                stroke=QPainterPathStroker();stroke.setWidth(p['gap']);path=path.subtracted(stroke.createStroke(path))
            result.append(Shape(path))
        return result
    raise ValueError(kind)


def _process(kind,p,a,b):
    rng=random.Random(int(p.get('seed',0)))
    if kind=='Output':return a
    if kind=='Merge':return a+b
    if kind=='Transform':return _mapped(a,_around(256+p['x'],256+p['y'],p['angle'],p['scale_x'],p['scale_y']))
    if kind=='Mirror':
        out=list(a)
        if p['axis'] in ('horizontal','both'):out+=_mapped(a,_around(256,256,0,-1,1))
        if p['axis'] in ('vertical','both'):out+=_mapped(out if p['axis']=='both' else a,_around(256,256,0,1,-1))
        return out
    if kind in ('Scatter','Grid','Radial'):
        copies=[]
        if kind=='Scatter':
            for i in range(int(p['count'])):
                if p['distribution']=='cluster':x,y=rng.gauss(256,TILE*p['spread']),rng.gauss(256,TILE*p['spread'])
                elif p['distribution']=='radial':
                    angle=rng.random()*math.tau;radius=p['radius']*math.sqrt(rng.random());x,y=256+math.cos(angle)*radius,256+math.sin(angle)*radius
                else:x,y=rng.random()*TILE,rng.random()*TILE
                copies.append((x,y,rng.uniform(-p['rotation'],p['rotation']),rng.uniform(p['min_scale'],p['max_scale']),rng.uniform(p['opacity_min'],1)))
        elif kind=='Grid':
            cols,rows=int(p['columns']),int(p['rows'])
            for row in range(rows):
                for col in range(cols):
                    x=(col+.5+(row%2)*p['offset']+(rng.random()-.5)*p['jitter'])*TILE/cols
                    y=(row+.5+(rng.random()-.5)*p['jitter'])*TILE/rows
                    copies.append((x,y,p['rotation'],p['scale'],1))
        else:
            for i in range(int(p['count'])):
                angle=p['start']+i*360/int(p['count']);rad=math.radians(angle)
                copies.append((256+math.cos(rad)*p['radius'],256+math.sin(rad)*p['radius'],angle if p['rotate']=='yes' else 0,p['scale'],1))
        if len(copies)*len(a)>MAX_SHAPES:raise ValueError('Too many instances. Reduce count or simplify the graph.')
        result=[]
        # Center each input group on its geometry bounds before instancing.
        bounds=QRectF()
        for shape in a:bounds=bounds.united(shape.path.boundingRect())
        center=bounds.center()
        for x,y,angle,scale,opacity in copies:
            t=QTransform();t.translate(x,y);t.rotate(angle);t.scale(scale,scale);t.translate(-center.x(),-center.y())
            result.extend(Shape(t.map(s.path),s.color,s.opacity*opacity) for s in a)
        return result
    if kind=='Colorize':
        ca,cb=QColor(p['color']),QColor(p['second']);result=[]
        for s in a:
            t=rng.random()*p['variation'];channels=[round(ca.getRgb()[i]*(1-t)+cb.getRgb()[i]*t) for i in range(3)]
            result.append(Shape(s.path,QColor(*channels).name(),s.opacity*p['opacity'],s.tiled,s.level))
        return result
    if kind=='Outline':
        stroke=QPainterPathStroker();stroke.setWidth(p['width']);stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return [Shape(stroke.createStroke(s.path),s.color,s.opacity,s.tiled,s.level) for s in a]
    if kind=='Warp':
        phase=rng.random()*math.tau;freq=int(p['frequency']);result=[]
        def displace(x,y):
            return QPointF(x+p['amount']*math.sin(y/TILE*math.tau*freq+phase),y+p['amount']*math.cos(x/TILE*math.tau*freq+phase))
        for s in a:
            path=QPainterPath();path.setFillRule(s.path.fillRule())
            for polygon in s.path.toSubpathPolygons():
                polygon = list(polygon)
                if not polygon:continue
                path.moveTo(displace(polygon[0].x(),polygon[0].y()))
                for start,end in zip(polygon,polygon[1:]):
                    steps=max(1,min(128,int(math.hypot(end.x()-start.x(),end.y()-start.y())/p['detail'])))
                    for i in range(1,steps+1):
                        f=i/steps;path.lineTo(displace(start.x()*(1-f)+end.x()*f,start.y()*(1-f)+end.y()*f))
                path.closeSubpath()
            result.append(Shape(path,s.color,s.opacity))
        return result
    if kind=='Boolean':
        if sum(s.path.elementCount() for s in a+b)>30000:raise ValueError('Boolean geometry is too complex; reduce instances first')
        left=QPainterPath();right=QPainterPath()
        for s in a:left=left.united(s.path)
        for s in b:right=right.united(s.path)
        operation=p['operation']
        path=left.united(right) if operation=='union' else left.intersected(right) if operation=='intersect' else left.subtracted(right) if operation=='subtract' else left.subtracted(right).united(right.subtracted(left))
        return [Shape(path,a[0].color if a else '#ffffff',a[0].opacity if a else 1)]
    raise ValueError(kind)


def _fields():
    try:
        from . import fields
    except ImportError as exc:  # numpy missing
        raise ValueError('Field nodes need numpy (pacman -S python-numpy)') from exc
    return fields


def _field(kind,p,n,inputs):
    F=_fields();a,b,c=(list(inputs)+[None,None,None])[:3]
    if kind=='Perlin':return F.perlin(n,p['frequency'],p['octaves'],p['persistence'],int(p['lacunarity']),p['mode'],p['stretch'],p['seed'])
    if kind=='Fibers':return F.fibers(n,p['count'],p['length'],p['thickness'],p['angle'],p['spread'],p['curl'],p['seed'])
    if kind=='Cracks':return F.cracks(n,p['count'],p['width'],p['mode'],p['jitter'],p['warp'],p['seed'])
    if kind=='Veins':return F.veins(n,p['kind'],int(p['rings']),p['distortion'],p['detail'],p['sharpness'],p['direction'],p['seed'])
    if kind=='Weave':return F.weave(n,p['threads'],p['pattern'],p['width'],p['roundness'],p['variation'],p['seed'])
    if kind=='Gradient':return F.gradient_field(n,p['kind'],p['angle'],p['repeat'])
    if kind=='Levels':return F.levels(a,p['low'],p['high'],p['gamma'],p['invert'],p['steps'],p['contrast'])
    if kind=='Blend':return F.blend(a,b,p['mode'],p['opacity'],c)
    if kind=='Field warp':return F.warp(a,b,p['amount'],p['mode'],p['angle'],p['turns'])
    if kind=='Multiscale':return F.multiscale(a,p['scales'],p['falloff'],p['mode'])
    if kind=='Blur':return F.blur(a,p['radius'],p['angle'],p['stretch'])
    if kind=='Erosion':return F.erosion(a,p['strength'],p['iterations'],p['angle'],p['streak'],p['seed'])
    if kind=='Tiles':return F.tiles(n,p['columns'],p['rows'],p['pattern'],p['gap'],p['bevel'],p['profile'],p['variation'],p['seed'])
    if kind=='Scales':return F.scales(n,p['columns'],p['rows'],p['overlap'],p['roundness'],p['variation'],p['seed'])
    if kind=='Pebbles':return F.pebbles(n,p['count'],p['gap'],p['roundness'],p['variation'],p['jitter'],p['seed'])
    if kind=='Stripes':return F.stripes(n,p['count'],p['angle'],p['sharpness'],p['wobble'],p['seed'])
    if kind=='Bevel':return F.bevel(a,p['threshold'],p['width'],p['profile'],p['keep_height'])
    if kind=='Slope blur':return F.slope_blur(a,b,p['amount'],int(p['samples']))
    if kind=='Histogram scan':return F.histogram_scan(a,p['position'],p['contrast'])
    if kind=='Symmetry':return F.symmetry(a,p['mode'])
    if kind=='Slope':return F.slope(a,p['depth'])
    if kind=='Curvature':return F.curvature(a,p['radius'],p['mode'])
    if kind=='Ambient occlusion':return F.ambient_occlusion(a,p['radius'],p['strength'])
    if kind=='Relief':return F.relief(a,p['angle'],p['elevation'],p['depth'],p['mix'])
    if kind=='Wear':return F.wear(a,p['amount'],p['edge_width'],p['breakup'],p['seed'])
    raise ValueError(kind)


def _loops_path(loops):
    F=_fields();path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
    for loop in loops:
        loop=F.simplify(loop);path.moveTo(*loop[0])
        for x,y in loop[1:]:path.lineTo(x,y)
        path.closeSubpath()
    return path


def _mix(low,high,t):
    a,b=QColor(low).getRgbF(),QColor(high).getRgbF()
    return QColor.fromRgbF(*(a[i]*(1-t)+b[i]*t for i in range(3))).name()


def _ramp_color(p,t):
    """Colour at t from a node's 2- or 3-colour ramp parameters."""
    if p.get('ramp')!='3 colours':return _mix(p['color_low'],p['color_high'],t)
    m=min(.99,max(.01,p['mid_position']))
    return _mix(p['color_low'],p['color_mid'],t/m) if t<=m else _mix(p['color_mid'],p['color_high'],(t-m)/(1-m))


def _contours(field,p):
    """Field → seamless vector bands / iso-lines / threshold region (even-odd paths)."""
    F = _fields()
    # A contour cannot contain information that is absent from its source
    # field.  Upsampling a 96 px interactive preview to a 320 px contour grid
    # used to create thousands of redundant path points before it was drawn or
    # exported.  Keep the author's requested detail for full-resolution fields,
    # while bounding previews and low-resolution graphs to their real data.
    detail = min(int(p['detail']), int(field.shape[0]), int(field.shape[1]))
    field = F.resample(field, detail)
    mode=p['mode'];result=[]
    if mode=='threshold':
        return [Shape(_loops_path(F.iso_loops(field,p['threshold'])),p['color_high'],p['opacity'],True)]
    count=int(p['levels'])
    if mode=='bands':
        base=QPainterPath();base.addRect(QRectF(0,0,TILE,TILE))
        result.append(Shape(base,_ramp_color(p,0),p['opacity'],True,0.0))
    for i in range(1,count):
        level=i/count;loops=F.iso_loops(field,level)
        if not loops:continue
        path=_loops_path(loops)
        if mode=='lines':
            stroker=QPainterPathStroker();stroker.setWidth(p['line_width']);stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            result.append(Shape(stroker.createStroke(path),_ramp_color(p,level),p['opacity'],True))
        else:result.append(Shape(path,_ramp_color(p,level),p['opacity'],True,level))
    return result


def _bridge(kind,p,shapes,field):
    F=_fields()
    import numpy as np
    if kind=='Mask by field':
        if not shapes:return []
        centers=[s.path.boundingRect().center() for s in shapes]
        values=F.sample(field,np.array([c.x()%TILE for c in centers]),np.array([c.y()%TILE for c in centers]))
        values=np.clip((values-.5)*p['contrast']+.5,0,1)
        if p['invert']=='yes':values=1-values
        out=[]
        for s,v in zip(shapes,values.tolist()):
            if v<p['threshold'] or v<=.002:continue
            out.append(Shape(s.path,s.color,s.opacity if p['mode']=='cull' else s.opacity*v,s.tiled,s.level))
        return out
    if kind=='Color by field':
        if not shapes:return []
        centers=[s.path.boundingRect().center() for s in shapes]
        values=F.sample(field,np.array([c.x()%TILE for c in centers]),np.array([c.y()%TILE for c in centers]))
        values=np.clip((values-.5)*p['contrast']+.5,0,1);out=[]
        for s,v in zip(shapes,values.tolist()):
            colour=_ramp_color(p,v)
            if p['mix']<1:colour=_mix(s.color,colour,p['mix'])
            out.append(Shape(s.path,colour,s.opacity,s.tiled,s.level))
        return out
    if kind=='Displace by field':
        gx,gy=F.gradient(F.blur(field,4));rad=math.radians(p['angle']);result=[]
        for s in shapes:
            path=QPainterPath();path.setFillRule(s.path.fillRule())
            for polygon in s.path.toSubpathPolygons():
                pts=[(q.x(),q.y()) for q in polygon]
                if len(pts)<2:continue
                dense=[pts[0]]
                for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
                    steps=max(1,min(128,int(math.hypot(x1-x0,y1-y0)/p['detail'])))
                    dense.extend((x0+(x1-x0)*i/steps,y0+(y1-y0)*i/steps) for i in range(1,steps+1))
                arr=np.array(dense,dtype=np.float64);x=arr[:,0]%TILE;y=arr[:,1]%TILE
                v=(F.sample(field,x,y)-.5)*2*p['amount']
                if p['mode']=='gradient':
                    ax,ay=F.sample(gx,x,y),F.sample(gy,x,y);length=np.sqrt(ax*ax+ay*ay)+1e-9
                    dx,dy=ax/length*v,ay/length*v
                else:dx,dy=v*math.cos(rad),v*math.sin(rad)
                moved=arr+np.stack([dx,dy],1)
                path.moveTo(float(moved[0,0]),float(moved[0,1]))
                for px,py in moved[1:].tolist():path.lineTo(px,py)
                path.closeSubpath()
            result.append(Shape(path,s.color,s.opacity))
        return result
    if kind=='Flow scatter':
        rng=np.random.default_rng(int(p['seed']));count=int(p['count'])
        gx,gy=F.gradient(F.blur(field,6))
        tries=count*12;x=rng.random(tries)*TILE;y=rng.random(tries)*TILE
        keep=rng.random(tries)<np.clip(F.sample(field,x,y),0,1)**p['density']
        x,y=x[keep][:count],y[keep][:count]
        heading=np.degrees(np.arctan2(F.sample(gy,x,y),F.sample(gx,x,y)))
        heading=heading+90 if p['align']=='along' else heading if p['align']=='across' else heading*0
        heading=heading+rng.uniform(-p['jitter'],p['jitter'],len(x))
        scales=rng.uniform(p['min_scale'],max(p['min_scale'],p['max_scale']),len(x))
        if len(x)*len(shapes)>MAX_SHAPES:raise ValueError('Too many instances. Reduce count or simplify the graph.')
        bounds=QRectF()
        for s in shapes:bounds=bounds.united(s.path.boundingRect())
        center=bounds.center();result=[]
        for px,py,angle,scale in zip(x.tolist(),y.tolist(),heading.tolist(),scales.tolist()):
            t=QTransform();t.translate(px,py);t.rotate(angle);t.scale(scale,scale);t.translate(-center.x(),-center.y())
            result.extend(Shape(t.map(s.path),s.color,s.opacity) for s in shapes)
        return result
    raise ValueError(kind)


# ── Evaluation with a per-node cache ──────────────────────────────────────
_CACHE=OrderedDict();_CACHE_LOCK=threading.Lock();_CACHE_SIZE=192


def _cache_get(key):
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key);return True,_CACHE[key]
    return False,None


def _cache_put(key,value):
    with _CACHE_LOCK:
        _CACHE[key]=value;_CACHE.move_to_end(key)
        while len(_CACHE)>_CACHE_SIZE:_CACHE.popitem(last=False)


def clear_cache():
    with _CACHE_LOCK:_CACHE.clear()


def _params(node):
    p={k:copy.deepcopy(s[2]) for k,s in SCHEMA[node['type']]['params'].items()};p.update(node.get('params',{}));return p


def _node_key(node,p,child_keys,resolution):
    extra=''
    if node['type']=='Image' and p.get('path'):
        try:stat=os.stat(p['path']);extra=f'{stat.st_mtime_ns}:{stat.st_size}'
        except OSError:extra='missing'
    if node['type']=='Group':extra=json.dumps(node.get('group'),sort_keys=True,default=str)
    raw=json.dumps([node['type'],p,child_keys,resolution,extra],sort_keys=True,default=str)
    return hashlib.sha1(raw.encode()).hexdigest()


def _qimage_array(image):
    """QImage → uint8 array (h, w, 4) RGBA."""
    import numpy as np
    img=image.convertToFormat(QImage.Format.Format_RGBA8888)
    w,h,bpl=img.width(),img.height(),img.bytesPerLine()
    data=bytes(img.constBits())[:bpl*h]
    return np.frombuffer(data,np.uint8).reshape(h,bpl)[:,:w*4].reshape(h,w,4).copy()


def _channel(rgba,channel):
    import numpy as np
    rgba=rgba.astype(np.float32)/255
    if channel=='alpha':return rgba[...,3]
    if channel in ('red','green','blue'):return rgba[...,'rgb'.index(channel[0])]*rgba[...,3]
    return (rgba[...,0]*.2126+rgba[...,1]*.7152+rgba[...,2]*.0722)*rgba[...,3]


def _image_field(p,resolution):
    if not p['path']:raise ValueError('Image: choose an image file')
    image=QImage(p['path'])
    if image.isNull():raise ValueError(f"Image: cannot read {Path(p['path']).name}")
    if image.width()*image.height()>64_000_000:raise ValueError('Image: picture is too large (64 MP max)')
    F=_fields();field=F.from_image(_channel(_qimage_array(image),p['channel']),resolution,p['tileable']=='yes',p['blend'])
    return 1-field if p['invert']=='yes' else field


def _rasterize(shapes,p,resolution):
    """Vector geometry → field (seamless): coverage or luminance, optional softening."""
    F=_fields();settings={'settings':{'seamless':True,'background':'transparent'}}
    image=render(settings,resolution,mask=p['mode']=='coverage',shapes=shapes)
    field=_channel(_qimage_array(image),'alpha' if p['mode']=='coverage' else 'luminance')
    if p['blur']:field=F.blur(field,p['blur'])
    return 1-field if p['invert']=='yes' else field


def _compute(node,p,args,child_keys,resolution,depth):
    kind=node['type'];spec=node_spec(node)
    if kind=='Group':
        inner=copy.deepcopy(node['group']['graph']);inner.setdefault('settings',{})['field_resolution']=resolution
        inject={i:(args[i],child_keys[i]) for i in range(len(args))}
        values,_,errors,lookup,inputs,output=_run(inner,inject=inject,depth=depth+1)
        return values[inputs[output][0]]
    if spec['out']=='field':
        if kind=='Image':return _image_field(p,resolution)
        if kind=='Rasterize':return _rasterize(args[0] or [],p,resolution)
        return _field(kind,p,resolution,args)
    if kind=='Output':
        if depth>0:return args[0]
        if args[0] is not None and not isinstance(args[0],list):
            defaults={k:s[2] for k,s in SCHEMA['Contours']['params'].items()}
            return _contours(args[0],{**defaults,'color_low':'#000000','color_high':'#ffffff'})
        return args[0] or []
    if kind=='Contours':return _contours(args[0],p)
    if kind in ('Mask by field','Displace by field','Flow scatter','Color by field'):return _bridge(kind,p,args[0] or [],args[1])
    if not spec['inputs']:return _generator(kind,p)
    return _process(kind,p,args[0] or [],(list(args)+[None])[1] or [])


def _run(graph,*,inject=None,partial=False,depth=0):
    lookup,inputs,order,output=validate(graph,partial=partial,_depth=depth)
    resolution=graph.get('settings',{}).get('field_resolution',256)
    values,keys,errors={},{},{}
    for nid in order:
        node=lookup[nid];spec=node_spec(node);p=_params(node);parents=inputs[nid]
        if any(pid not in values for pid in parents.values()):
            errors[nid]='An input node has an error';continue
        missing=[spec['port_names'][i] for i in range(spec['inputs']) if i not in spec['optional'] and i not in parents]
        if missing:errors[nid]=f"Connect input {', '.join(missing)}";continue
        args=[values.get(parents.get(i)) for i in range(spec['inputs'])]
        child=[keys.get(parents.get(i)) for i in range(spec['inputs'])]
        if node['type']=='Group input':
            index=int(p['index'])
            if not inject or index not in inject:errors[nid]='Group input outside a group';continue
            values[nid],keys[nid]=inject[index];continue
        key=_node_key(node,p,child,resolution)+str(depth if node['type']=='Output' else '')
        hit,value=_cache_get(key)
        if not hit:
            try:
                value=_compute(node,p,args,child,resolution,depth)
                if isinstance(value,list):
                    if len(value)>MAX_SHAPES:raise ValueError('Geometry budget exceeded (12,000 shapes)')
                    if sum(s.path.elementCount() for s in value)>800000:raise ValueError('Path detail budget exceeded')
            except Exception as exc:
                if not partial:raise
                errors[nid]=str(exc);continue
            _cache_put(key,value)
        values[nid]=value;keys[nid]=key
    return values,keys,errors,lookup,inputs,output


def evaluate(graph,*,keep_fields=False):
    values,_,_,_,_,output=_run(graph)
    return (values[output],values) if keep_fields else values[output]


def all_values(graph):
    """Values of every node that can be computed (thumbnails), plus per-node errors."""
    values,_,errors,_,_,_=_run(graph,partial=True)
    return values,errors


def node_value(graph,nid):
    values,errors=all_values(graph)
    if nid in errors:raise ValueError(errors[nid])
    return values.get(nid)


def output_field(graph):
    """(field, contour parameters or None) giving the Output colour, or (None, None) for pure geometry."""
    values,_,_,lookup,inputs,output=_run(graph)
    source=inputs[output].get(0)
    if source is None:return None,None
    kind=lookup[source]['type']
    if node_spec(lookup[source])['out']=='field':return values[source],None
    if kind=='Contours':return values[inputs[source][0]],_params(lookup[source])
    return None,None


def output_channels(graph):
    """Height / roughness / metallic fields (or constants) for PBR export."""
    values,_,_,lookup,inputs,output=_run(graph);p=_params(lookup[output])
    def port(i):
        source=inputs[output].get(i)
        return values[source] if source is not None else None
    height=port(1)
    if height is None:height=output_field(graph)[0]
    return {'height':height,'roughness':port(2),'metallic':port(3),'params':p}


def brush_field(graph,size):
    """Greyscale brush mask straight from the field (smooth, not posterised); None for geometry."""
    field,p=output_field(graph)
    if field is None or (p and p['mode']=='lines'):return None
    F=_fields();import numpy as np
    field=F.resample(field,size)
    if p and p['mode']=='threshold':field=F._smoothstep(p['threshold']-.01,p['threshold']+.01,field)
    return np.clip(field,0,1)


def _alpha_image(values):
    import numpy as np
    size=values.shape[0];rgba=np.empty((size,size,4),np.uint8);rgba[...,:3]=255
    rgba[...,3]=(np.clip(values,0,1)*255+.5).astype(np.uint8)
    return QImage(rgba.tobytes(),size,size,size*4,QImage.Format.Format_RGBA8888).copy()


def _gray_image(values):
    import numpy as np
    size=values.shape[0];data=(np.clip(values,0,1)*255+.5).astype(np.uint8)
    return QImage(data.tobytes(),size,size,size,QImage.Format.Format_Grayscale8).copy()


def _height(graph,size):
    channels=output_channels(graph)
    if channels['height'] is None:raise ValueError('Height maps need a field-based texture (Contours, a field into Output, or Output › Height)')
    return _fields().resample(channels['height'],size),channels


def height_image(graph,size):
    field,_=_height(graph,size);data=_fields().height_map16(field)
    return QImage(data.tobytes(),size,size,size*2,QImage.Format.Format_Grayscale16).copy()


def normal_image(graph,size,depth=None,convention='opengl'):
    field,channels=_height(graph,size)
    depth=channels['params']['normal_depth'] if depth is None else depth
    data=_fields().normal_map(field,depth,convention)
    return QImage(data.tobytes(),size,size,size*3,QImage.Format.Format_RGB888).copy()


def pbr_maps(graph,size,convention='opengl'):
    """Base colour, height (16-bit), normal, ambient occlusion, roughness and metallic maps."""
    import numpy as np
    F=_fields();field,channels=_height(graph,size);p=channels['params']
    maps={'basecolor':render(graph,size),'height':height_image(graph,size),'normal':normal_image(graph,size,None,convention),
          'ao':_gray_image(F.ambient_occlusion(field,p['ao_radius']))}
    for name in ('roughness','metallic'):
        value=channels[name]
        maps[name]=_gray_image(F.resample(value,size) if value is not None else np.full((size,size),p[name],np.float32))
    return maps


def field_preview(graph,nid,size=128):
    """Greyscale QImage of a field node's value (inspector thumbnail); None for geometry nodes."""
    lookup,_,_,_=validate(graph,partial=True)
    if nid not in lookup or node_spec(lookup[nid])['out']!='field':return None
    return _gray_image(_fields().resample(node_value(graph,nid),size))


def thumbnail(value,size=64,background='#24333b'):
    """Small preview of any node value: field greyscale or rendered geometry."""
    if value is None:return None
    if not isinstance(value,list):return _gray_image(_fields().resample(value,size))
    return render({'settings':{'seamless':True,'background':background}},size,shapes=value)


# ── Groups (sub-graphs) ───────────────────────────────────────────────────
def group_nodes(graph,ids,name='Group'):
    """Pack the selected nodes into one Group node. Returns (new graph, group id)."""
    ids=set(ids);g=copy.deepcopy(graph);nodes={n['id']:n for n in g['nodes']}
    if not ids or any(i not in nodes for i in ids):raise ValueError('Select the nodes to group')
    if any(nodes[i]['type']=='Output' for i in ids):raise ValueError('The Output node cannot be grouped')
    edges=g['edges']
    incoming=[e for e in edges if e['to'] in ids and e['from'] not in ids]
    outgoing=[e for e in edges if e['from'] in ids and e['to'] not in ids]
    sources=sorted({e['from'] for e in outgoing})
    if not sources:
        sources=[i for i in ids if not any(e['from']==i and e['to'] in ids for e in edges)]
    if len(sources)!=1:raise ValueError('A group needs exactly one node whose result leaves the group')
    out_id=sources[0];external=list(dict.fromkeys(e['from'] for e in incoming))
    if len(external)>4:raise ValueError('A group accepts at most 4 inputs')
    inner_nodes=[copy.deepcopy(nodes[i]) for i in nodes if i in ids]
    inner_edges=[copy.deepcopy(e) for e in edges if e['from'] in ids and e['to'] in ids]
    used={n['id'] for n in inner_nodes};ports=[];names=[]
    left=min(n.get('x',0) for n in inner_nodes);top=min(n.get('y',0) for n in inner_nodes)
    for index,source in enumerate(external):
        gid=f'group_in_{index}'
        while gid in used:gid+='_'
        used.add(gid);kind=node_spec(nodes[source])['out']
        inner_nodes.append({'id':gid,'type':'Group input','input_type':kind,'x':left-260,'y':top+index*130,'params':{'index':index}})
        ports.append(kind);names.append(nodes[source].get('name') or nodes[source]['type'])
        inner_edges+=[{'from':gid,'to':e['to'],'input':e.get('input',0)} for e in incoming if e['from']==source]
    out_node='group_out'
    while out_node in used:out_node+='_'
    right=max(n.get('x',0) for n in inner_nodes)
    inner_nodes.append({'id':out_node,'type':'Output','x':right+260,'y':top,'params':{}})
    inner_edges.append({'from':out_id,'to':out_node,'input':0})
    inner={'version':1,'nodes':inner_nodes,'edges':inner_edges,
           'settings':{'field_resolution':g.get('settings',{}).get('field_resolution',256)}}
    group_id='g'+uuid.uuid4().hex[:7]
    xs=[nodes[i].get('x',0) for i in ids];ys=[nodes[i].get('y',0) for i in ids]
    group={'id':group_id,'type':'Group','name':name,'x':sum(xs)/len(xs),'y':sum(ys)/len(ys),'params':{},
           'group':{'graph':inner,'ports':ports,'port_names':[n[:14] for n in names],'out':node_spec(nodes[out_id])['out']}}
    g['nodes']=[n for n in g['nodes'] if n['id'] not in ids]+[group]
    kept=[e for e in edges if e['from'] not in ids and e['to'] not in ids]
    kept+=[{'from':source,'to':group_id,'input':index} for index,source in enumerate(external)]
    kept+=[{'from':group_id,'to':e['to'],'input':e.get('input',0)} for e in outgoing]
    g['edges']=kept
    g['exposed']=[e for e in g.get('exposed',[]) if e.get('node') not in ids]
    validate(g,partial=True)
    return g,group_id


def ungroup(graph,group_id):
    """Expand a Group node back into its nodes. Returns (new graph, ids of the restored nodes)."""
    g=copy.deepcopy(graph);node=next((n for n in g['nodes'] if n['id']==group_id),None)
    if not node or node['type']!='Group':raise ValueError('Select a group to ungroup')
    inner=node['group']['graph'];kinds={n['id']:n['type'] for n in inner['nodes']}
    rename={nid:f'{group_id}_{nid}' for nid,kind in kinds.items() if kind not in ('Group input','Output')}
    left=min((n.get('x',0) for n in inner['nodes'] if n['id'] in rename),default=0)
    top=min((n.get('y',0) for n in inner['nodes'] if n['id'] in rename),default=0)
    for inner_node in inner['nodes']:
        if inner_node['id'] in rename:
            copy_node=copy.deepcopy(inner_node);copy_node['id']=rename[inner_node['id']]
            copy_node['x']=node.get('x',0)+inner_node.get('x',0)-left;copy_node['y']=node.get('y',0)+inner_node.get('y',0)-top
            g['nodes'].append(copy_node)
    feeds={e['input']:e['from'] for e in g['edges'] if e['to']==group_id}
    index_of={n['id']:int(n.get('params',{}).get('index',0)) for n in inner['nodes'] if n['type']=='Group input'}
    out_source=next(rename[e['from']] for e in inner['edges'] if kinds[e['to']]=='Output' and e.get('input',0)==0)
    edges=[e for e in g['edges'] if e['to']!=group_id and e['from']!=group_id]
    for e in inner['edges']:
        if kinds[e['to']]=='Output':continue
        if e['from'] in index_of:
            source=feeds.get(index_of[e['from']])
            if source:edges.append({'from':source,'to':rename[e['to']],'input':e.get('input',0)})
        else:edges.append({'from':rename[e['from']],'to':rename[e['to']],'input':e.get('input',0)})
    edges+=[{'from':out_source,'to':e['to'],'input':e.get('input',0)} for e in g['edges'] if e['from']==group_id]
    g['edges']=edges;g['nodes']=[n for n in g['nodes'] if n['id']!=group_id]
    g['exposed']=[e for e in g.get('exposed',[]) if e.get('node')!=group_id]
    validate(g,partial=True)
    return g,list(rename.values())


def duplicate_nodes(graph,ids,offset=40):
    """Copies of the given nodes (and the links between them) with fresh ids."""
    g=copy.deepcopy(graph);ids=[n['id'] for n in g['nodes'] if n['id'] in set(ids) and n['type']!='Output']
    mapping={nid:uuid.uuid4().hex[:8] for nid in ids};added=[]
    for node in [n for n in g['nodes'] if n['id'] in mapping]:
        clone=copy.deepcopy(node);clone['id']=mapping[node['id']];clone['x']=node.get('x',0)+offset;clone['y']=node.get('y',0)+offset
        added.append(clone)
    edges=[{'from':mapping[e['from']],'to':mapping[e['to']],'input':e.get('input',0)} for e in g['edges']
           if e['from'] in mapping and e['to'] in mapping]
    return added,edges


def exposed_controls(graph):
    """[(node, key, spec, label)] for the parameters exposed on the quick-controls panel."""
    lookup={n['id']:n for n in graph.get('nodes',[])};out=[]
    for entry in graph.get('exposed',[]):
        node=lookup.get(entry.get('node'))
        if node and entry.get('param') in SCHEMA[node['type']]['params']:
            spec=SCHEMA[node['type']]['params'][entry['param']]
            out.append((node,entry['param'],spec,entry.get('label') or f"{node.get('name') or node['type']} · {spec[0]}"))
    return out


def _smooth_image(graph,size):
    """Continuous (non-posterised) raster of a field-based texture, or None."""
    field,p=output_field(graph)
    if field is None or (p is not None and p['mode']!='bands'):return None
    import numpy as np
    F=_fields();values=F.resample(field,size)
    if p is None:rgb=np.repeat(values[...,None],3,2)
    else:
        def c(h):return [v for v in QColor(h).getRgbF()[:3]]
        rgb=F.ramp(values,c(p['color_low']),c(p['color_high']),c(p['color_mid']) if p.get('ramp')=='3 colours' else None,p['mid_position'])
    opacity=p['opacity'] if p else 1.0
    background=graph.get('settings',{}).get('background','#202b30')
    rgba=np.empty((size,size,4),np.float32);rgba[...,:3]=rgb;rgba[...,3]=1.0
    if opacity<1:
        if background=='transparent':rgba[...,3]=opacity
        else:rgba[...,:3]=rgb*opacity+np.array(c(background),np.float32)*(1-opacity)
    data=(np.clip(rgba,0,1)*255+.5).astype(np.uint8)
    return QImage(data.tobytes(),size,size,size*4,QImage.Format.Format_RGBA8888).copy()


def wrapped(shapes,seamless=True):
    if not seamless:return shapes
    out=[];tile=QRectF(0,0,TILE,TILE)
    for shape in shapes:
        if shape.tiled:
            out.append(shape);continue
        bounds=shape.path.boundingRect()
        xs=range(math.floor(-bounds.right()/TILE)+1,math.ceil((TILE-bounds.left())/TILE))
        ys=range(math.floor(-bounds.bottom()/TILE)+1,math.ceil((TILE-bounds.top())/TILE))
        if len(xs)*len(ys)>256:raise ValueError('Geometry is too large for tile wrapping')
        for x in xs:
            for y in ys:
                path=QTransform.fromTranslate(x*TILE,y*TILE).map(shape.path)
                if path.boundingRect().intersects(tile):out.append(Shape(path,shape.color,shape.opacity))
        if len(out)>MAX_SHAPES*4:raise ValueError('Too many wrapped shapes')
    return out


def render(graph,size=512,*,mask=False,shapes=None):
    if not isinstance(size,int) or not 16<=size<=8192:raise ValueError('Resolution must be 16–8192 pixels')
    image=QImage(size,size,QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull():raise MemoryError('Insufficient memory for this resolution')
    image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.scale(size/TILE,size/TILE)
    painter.setClipRect(QRectF(0,0,TILE,TILE));painter.setPen(Qt.PenStyle.NoPen)
    settings=graph.get('settings',{})
    if not mask and settings.get('smooth') and graph.get('nodes'):
        smooth=_smooth_image(graph,size)
        if smooth is not None:
            painter.end();return smooth
    if not mask and settings.get('background','#202b30')!='transparent':painter.fillRect(QRectF(0,0,TILE,TILE),QColor(settings.get('background','#202b30')))
    try:
        for shape in wrapped(evaluate(graph) if shapes is None else shapes,settings.get('seamless',True)):
            if mask and shape.level is not None:
                # Nested bands: each replaces the one below, so alpha = field level (not a white square).
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source);painter.setOpacity(1)
                painter.setBrush(QColor.fromRgbF(1,1,1,max(0.,min(1.,shape.level*shape.opacity))))
            else:
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                painter.setOpacity(shape.opacity);painter.setBrush(QColor('white' if mask else shape.color))
            painter.drawPath(shape.path)
    finally:painter.end()
    return image


def png_bytes(image):
    data=QByteArray();stream=QBuffer(data);stream.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(stream,'PNG'):raise ValueError('PNG encoder unavailable')
    return bytes(data)


def path_svg(path):
    commands=[];i=0
    while i<path.elementCount():
        e=path.elementAt(i)
        if e.isMoveTo():commands.append(f'M {e.x:.5f} {e.y:.5f}')
        elif e.isLineTo():commands.append(f'L {e.x:.5f} {e.y:.5f}')
        else:
            a,b=path.elementAt(i+1),path.elementAt(i+2);commands.append(f'C {e.x:.5f} {e.y:.5f} {a.x:.5f} {a.y:.5f} {b.x:.5f} {b.y:.5f}');i+=2
        i+=1
    return ' '.join(commands)


def svg(graph):
    settings=graph.get('settings',{});background=settings.get('background','#202b30')
    lines=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">',
           '<defs><clipPath id="tile"><rect width="512" height="512"/></clipPath></defs>', '<g clip-path="url(#tile)">']
    if background!='transparent':lines.append(f'<rect width="512" height="512" fill="{escape(QColor(background).name())}"/>')
    for shape in wrapped(evaluate(graph),settings.get('seamless',True)):
        rule='evenodd' if shape.path.fillRule()==Qt.FillRule.OddEvenFill else 'nonzero'
        lines.append(f'<path d="{path_svg(shape.path)}" fill="{shape.color}" fill-opacity="{shape.opacity:.5f}" fill-rule="{rule}"/>')
    return '\n'.join(lines+['</g></svg>'])


def brush_payload(graph,name='Procedural texture brush',size=512,role='tip'):
    if role not in ('tip','grain'):raise ValueError('Choose brush tip or grain')
    if not isinstance(size,int) or not 16<=size<=4096:raise ValueError('Brush masks must be 16–4096 pixels')
    smooth=brush_field(graph,size)
    mask=_alpha_image(smooth) if smooth is not None else render(graph,size,mask=True)
    payload = {'format':'CreativeSystemBrushPreset','version':3,'name':name,'category':'Texture Creator','favorite':False,
        'size':64.0,'opacity':1.0,'flow':1.0,'hardness':1.0,'roundness':1.0,'spacing':.18,'pressureSize':True,
        'color':[35,42,48,255], '_csbr_bitmap_tip_png':base64.b64encode(png_bytes(mask)).decode(),
        '_procedural_texture':copy.deepcopy(graph), '_procedural_texture_role':role}
    if role == 'grain':
        gray=QImage(size,size,QImage.Format.Format_RGB32);gray.fill(QColor('black'))
        painter=QPainter(gray);painter.drawImage(0,0,mask);painter.end()
        payload.pop('_csbr_bitmap_tip_png',None)
        payload['_csbr_texture_png']=base64.b64encode(png_bytes(gray)).decode()
        payload.update(textureStrength=1.0,textureScale=1.0)
    return payload


def save_graph(graph,path):
    validate(graph);Path(path).write_text(json.dumps({'format':'ExistenceProceduralTexture','version':1,'content':graph},indent=2),encoding='utf-8')


def load_graph(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('format') not in ('ExistenceProceduralTexture','StarDustResource','creativesysteme.stellardust.document','creativesysteme.stardust.resource'):raise ValueError('Not a procedural texture document')
    graph=data.get('content',data);validate(graph);return graph


# ── Material presets built on continuous fields ───────────────────────────
# Each entry: nodes as (type, params) and edges as (from, to, input).
MATERIALS={
 'Realistic wood':([('Veins',dict(kind='wood',rings=14,distortion=.45,detail=2,sharpness=1.8)),
                    ('Perlin',dict(frequency=2,octaves=5,stretch=12,seed=21)),
                    ('Field warp',dict(mode='value',amount=5,angle=90)),
                    ('Fibers',dict(count=2200,length=220,thickness=.7,angle=0,spread=3,curl=.08)),
                    ('Blend',dict(mode='subtract',opacity=.22)),
                    ('Contours',dict(levels=24,ramp='3 colours',color_low='#4a2812',color_mid='#9a6332',color_high='#dcae74',mid_position=.45,detail=256)),('Output',{})],
                   [(0,2,0),(1,2,1),(2,4,0),(3,4,1),(4,5,0),(5,6,0)]),
 'Leather':([('Cracks',dict(mode='crackle',count=300,width=.8,jitter=.45,warp=.45)),
             ('Blur',dict(radius=1.5)),
             ('Perlin',dict(frequency=5,octaves=5,seed=9)),
             ('Blend',dict(mode='soft light',opacity=.6)),
             ('Levels',dict(low=.15,gamma=1.2,contrast=1.05)),
             ('Relief',dict(angle=-135,elevation=50,depth=2.5,mix=.65)),
             ('Contours',dict(levels=20,ramp='3 colours',color_low='#24130c',color_mid='#6b4029',color_high='#a87652',detail=320)),('Output',{})],
            [(0,1,0),(1,3,0),(2,3,1),(3,4,0),(4,5,0),(5,6,0),(6,7,0)]),
 'Fibrous paper':([('Perlin',dict(frequency=16,octaves=4,mode='turbulence',seed=4)),
                   ('Levels',dict(contrast=.35)),
                   ('Fibers',dict(count=4000,length=55,thickness=.6,spread=180,curl=.6)),
                   ('Blend',dict(mode='screen',opacity=.85)),
                   ('Contours',dict(levels=20,color_low='#cdbf9f',color_high='#fbf7ec',detail=320)),('Output',{})],
                  [(0,1,0),(1,3,0),(2,3,1),(3,4,0),(4,5,0)]),
 'Woven fabric':([('Weave',dict(pattern='twill',threads=24)),
                  ('Perlin',dict(frequency=12,octaves=3,seed=2)),
                  ('Blend',dict(mode='multiply',opacity=.25)),
                  ('Relief',dict(angle=-120,elevation=55,depth=2,mix=.5)),
                  ('Contours',dict(levels=18,ramp='3 colours',color_low='#142a44',color_mid='#3d6390',color_high='#a9c2de',detail=288)),('Output',{})],
                 [(0,2,0),(1,2,1),(2,3,0),(3,4,0),(4,5,0)]),
 'Marble':([('Veins',dict(kind='marble',rings=1,distortion=.9,detail=2,sharpness=10)),
            ('Perlin',dict(frequency=2,octaves=5,seed=12)),
            ('Field warp',dict(mode='value',amount=26,angle=45)),
            ('Levels',dict(invert='yes',gamma=1.6)),
            ('Perlin',dict(frequency=3,octaves=6,seed=40)),
            ('Blend',dict(mode='multiply',opacity=.18)),
            ('Contours',dict(levels=24,color_low='#5f5b57',color_high='#f4f1ec',detail=256)),('Output',{})],
           [(0,2,0),(1,2,1),(2,3,0),(3,5,0),(4,5,1),(5,6,0),(6,7,0)]),
 'Worn bricks':([('Bricks',{}),('Colorize',dict(color='#9a4b32',second='#c27056',variation=.5)),
                 ('Perlin',dict(frequency=5,octaves=5,seed=31)),('Wear',dict(amount=.55,edge_width=8)),
                 ('Mask by field',dict(mode='opacity',invert='yes',contrast=2)),('Output',{})],
                [(0,1,0),(2,3,0),(1,4,0),(3,4,1),(4,5,0)]),
 'Cracked earth':([('Perlin',dict(frequency=3,octaves=6,seed=17)),('Erosion',dict(strength=.7,iterations=8)),
                   ('Cracks',dict(mode='cracks',count=35,width=2.5,warp=.8)),('Blend',dict(mode='subtract',opacity=.8)),
                   ('Relief',dict(angle=-135,elevation=40,depth=3,mix=.55)),
                   ('Contours',dict(levels=18,ramp='3 colours',color_low='#2e2016',color_mid='#8a6a4a',color_high='#d2b388',detail=224)),('Output',{})],
                  [(0,1,0),(1,3,0),(2,3,1),(3,4,0),(4,5,0),(5,6,0)]),
 'Hex tiles':([('Tiles',dict(pattern='hex',columns=8,rows=8,gap=3,bevel=7)),('Perlin',dict(frequency=8,octaves=4,seed=14)),
               ('Blend',dict(mode='multiply',opacity=.2)),('Relief',dict(angle=-135,elevation=45,depth=3,mix=.6)),
               ('Contours',dict(levels=20,ramp='3 colours',color_low='#1b2a2c',color_mid='#4f7c78',color_high='#cfe3dc',detail=256)),('Output',{})],
              [(0,2,0),(1,2,1),(2,3,0),(3,4,0),(4,5,0)]),
 'Fish scales':([('Scales',dict(columns=8,rows=14,overlap=.5)),('Relief',dict(angle=-120,elevation=50,depth=3,mix=.7)),
                 ('Contours',dict(levels=22,ramp='3 colours',color_low='#0e2a2a',color_mid='#2f7f73',color_high='#d6f2c8',detail=288)),('Output',{})],
                [(0,1,0),(1,2,0),(2,3,0)]),
 'Pebble path':([('Pebbles',dict(count=70,gap=.18)),('Relief',dict(angle=-135,elevation=45,depth=3,mix=.65)),
                 ('Ambient occlusion',dict(radius=14)),('Blend',dict(mode='multiply',opacity=.7)),
                 ('Contours',dict(levels=22,ramp='3 colours',color_low='#2b2622',color_mid='#7d7166',color_high='#d9d0c4',detail=288)),('Output',{})],
                [(0,1,0),(0,2,0),(1,3,0),(2,3,1),(3,4,0),(4,5,0)]),
 'Bevelled bricks':([('Bricks',dict(gap=6,roundness=2)),('Rasterize',dict(mode='coverage')),('Bevel',dict(width=7)),
                     ('Perlin',dict(frequency=10,octaves=4,seed=8)),('Blend',dict(mode='multiply',opacity=.25)),
                     ('Relief',dict(angle=-135,elevation=45,depth=3,mix=.6)),
                     ('Contours',dict(levels=20,ramp='3 colours',color_low='#2a1712',color_mid='#8a4532',color_high='#d49478',detail=256)),
                     ('Output',dict(roughness=.8))],
                    [(0,1,0),(1,2,0),(2,4,0),(3,4,1),(4,5,0),(5,6,0),(6,7,0),(4,7,1)]),
 'Flow lines':([('Shape',dict(shape='ellipse',size=60,aspect=.12)),('Perlin',dict(frequency=2,octaves=3,seed=5)),
                ('Flow scatter',dict(count=900,align='along',density=.6,min_scale=.3,max_scale=.8)),
                ('Colorize',dict(color='#dfe8e4',second='#7fb3a6',variation=.7)),('Output',{})],
               [(0,2,0),(1,2,1),(2,3,0),(3,4,0)]),
}


def _material(name):
    specs,links=MATERIALS[name];nodes=[]
    for index,(kind,params) in enumerate(specs):
        node=make_node(kind,index);node['params'].update(params)
        node['x']=80+(index%4)*240;node['y']=80+(index//4)*170
        nodes.append(node)
    edges=[{'from':nodes[a]['id'],'to':nodes[b]['id'],'input':port} for a,b,port in links]
    return {'version':1,'nodes':nodes,'edges':edges,
            'settings':{'seamless':True,'background':'#24333b','resolution':1024,'seed':42,'field_resolution':256}}


def preset(name='Terrazzo'):
    if name in MATERIALS:return _material(name)
    kinds={'Cloud field':['Noise','Colorize','Output'], 'Terrazzo':['Shape','Scatter','Colorize','Output'],'Halftone':['Shape','Grid','Colorize','Output'],
           'Paper grain':['Shape','Scatter','Colorize','Output'],'Woven lines':['Waves','Mirror','Colorize','Output'],
           'Woodcut':['Waves','Warp','Colorize','Output'],'Cellular stone':['Voronoi','Colorize','Output'],
           'Brickwork':['Bricks','Colorize','Output'],'Brush bloom':['Shape','Radial','Warp','Colorize','Output'],
           'Organic stamp':['Shape','Warp','Colorize','Output'],'Contour rings':['Shape','Grid','Outline','Colorize','Output']}
    if name not in kinds:raise ValueError('Unknown preset')
    nodes=[make_node(kind,i) for i,kind in enumerate(kinds[name])]
    graph={'version':1,'nodes':nodes,'edges':[{'from':a['id'],'to':b['id'],'input':0} for a,b in zip(nodes,nodes[1:])],
           'settings':{'seamless':name not in ('Brush bloom','Organic stamp'),'background':'#24333b','resolution':1024,'seed':42}}
    for node in nodes:
        p=node['params'];kind=node['type']
        if kind=='Shape':
            if name=='Terrazzo':p.update(shape='polygon',sides=5,size=130)
            if name=='Paper grain':p.update(shape='ellipse',size=20,aspect=.6)
            if name=='Brush bloom':p.update(shape='ellipse',size=210,aspect=.28)
            if name=='Organic stamp':p.update(shape='blob',size=360,sides=21,roughness=.45)
            if name=='Contour rings':p.update(shape='ring',size=150,inner=.65)
        if kind=='Scatter' and name=='Paper grain':p.update(count=1500,min_scale=.04,max_scale=.8,opacity_min=.08)
        if kind=='Grid' and name=='Contour rings':p.update(columns=4,rows=4,scale=.85)
        if kind=='Waves' and name=='Woven lines':p.update(count=48,amplitude=3,width=2,frequency=8)
        if kind=='Waves' and name=='Woodcut':p.update(count=40,amplitude=22,frequency=2,width=2)
        if kind=='Colorize' and name=='Paper grain':p.update(color='#efe2c1',second='#b6ab96',opacity=.5)
    if name=='Paper grain':graph['settings']['background']='#746b58'
    if not graph['settings']['seamless']:graph['settings']['background']='transparent'
    return graph

PRESETS=['Cloud field','Terrazzo','Halftone','Paper grain','Woven lines','Woodcut','Cellular stone','Brickwork','Brush bloom','Organic stamp','Contour rings']+list(MATERIALS)
