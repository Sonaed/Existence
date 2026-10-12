"""Existence-owned Texture Creator UI, hosted by StarDust."""
from __future__ import annotations
import copy
import json
import math
import os
import tempfile
import uuid
from pathlib import Path
from PySide6.QtCore import QObject,QPointF,QRectF,Qt,QTimer,Signal,QRunnable,QThreadPool
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QBrush,QImage,QTransform,QKeySequence,QPixmap
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QSplitter,QLabel,QPushButton,QComboBox,QCheckBox,
 QSpinBox,QDoubleSpinBox,QFormLayout,QScrollArea,QFileDialog,QMessageBox,QGraphicsView,QGraphicsScene,
 QGraphicsItem,QGraphicsRectItem,QGraphicsEllipseItem,QGraphicsPathItem,QGraphicsSimpleTextItem,QSizePolicy,
 QGraphicsPixmapItem,QGroupBox,QLineEdit,QCompleter,QApplication,QToolButton,QInputDialog)
from modules.creator_ui import History,theme
from . import engine


def create_creator(host=None):return TextureCreator(host or {})


class Preview(QWidget):
    def __init__(self,creator):
        super().__init__();self.creator=creator;self.setMinimumSize(200,200);self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#151b21'))
        size=min(self.width()-24,self.height()-24);ox=(self.width()-size)/2;oy=(self.height()-size)/2
        for y in range(0,int(size),16):
            for x in range(0,int(size),16):p.fillRect(QRectF(ox+x,oy+y,min(16,size-x),min(16,size-y)),QColor('#414950' if (x//16+y//16)%2 else '#353c43'))
        image=self.creator.mask if self.creator.show_mask else self.creator.image
        if not image.isNull():
            count=3 if self.creator.show_repeat else 1
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            for row in range(count):
                for col in range(count):p.drawImage(QRectF(ox+col*size/count,oy+row*size/count,size/count,size/count),image)
            if count==3:
                p.setPen(QPen(QColor('#65d3b6'),.8,Qt.PenStyle.DashLine))
                for i in (1,2):
                    p.drawLine(QPointF(ox+i*size/3,oy),QPointF(ox+i*size/3,oy+size))
                    p.drawLine(QPointF(ox,oy+i*size/3),QPointF(ox+size,oy+i*size/3))
        else:
            p.setPen(QColor('#a5b3bd'));p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Building geometry…')
        p.end()


PORT_COLORS={'geometry':'#91e2ca','field':'#f2b56b','any':'#cfd8dc'}


def port_type(node,index,output):
    spec=engine.node_spec(node)
    return spec['out'] if output else spec['ports'][index]


class Port(QGraphicsEllipseItem):
    def __init__(self,node,index,output=False):
        super().__init__(-6,-6,12,12,node);self.node=node;self.index=index;self.output=output
        spec=engine.node_spec(node.data);self.kind=port_type(node.data,index,output)
        self.setPos(196 if output else 0,58+index*22)
        optional=not output and index in spec['optional']
        self.setBrush(QColor('#192228') if optional else QColor(PORT_COLORS[self.kind]))
        self.setPen(QPen(QColor(PORT_COLORS[self.kind]) if optional else QColor('#121a20'),2));self.setZValue(5)
        if output:self.setToolTip(f'{self.kind.title()} output')
        else:
            name=spec['port_names'][index]
            self.setToolTip(f'{name} · {self.kind} input'+(' (optional)' if optional else ''))
            if spec['inputs']>1 or name not in 'AB':
                label=QGraphicsSimpleTextItem(name,node);label.setBrush(QColor('#9fb3bd'));label.setPos(12,51+index*22)


class Node(QGraphicsRectItem):
    THUMB=54
    def __init__(self,scene,data):
        spec=engine.node_spec(data);inputs=spec['inputs']
        super().__init__(0,0,196,max(104,72+inputs*22));self.data=data;self.owner=scene;self.nid=data['id']
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemIsSelectable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setBrush(QColor('#28343e'));self.setPen(QPen(QColor('#4a606c'),1))
        title=data.get('name') or data['type']
        self.title=QGraphicsSimpleTextItem(title if len(title)<=20 else title[:19]+'…',self);self.title.setBrush(QColor('#eff6f6'));self.title.setPos(14,13)
        desc=QGraphicsSimpleTextItem(spec['category'],self);desc.setBrush(QColor('#93a9b5'));desc.setPos(14,31)
        if spec['out']=='field':self.setBrush(QColor('#33302a'))
        if data['type']=='Group':self.setBrush(QColor('#2c2a3e'))
        self.thumb=QGraphicsPixmapItem(self);self.thumb.setPos(196-self.THUMB-10,40);self.thumb.setZValue(2)
        self.ports=[Port(self,i) for i in range(inputs)]
        self.output=None if data['type']=='Output' else Port(self,0,True)
        self.setPos(data.get('x',0),data.get('y',0))
        cached=scene.creator._thumbs.get(self.nid)
        if cached is not None:self.set_thumbnail(cached)
        self.set_error(scene.creator._node_errors.get(self.nid))
    def set_thumbnail(self,image):
        if image is None or image.isNull():self.thumb.setPixmap(QPixmap());return
        self.thumb.setPixmap(QPixmap.fromImage(image).scaled(self.THUMB,self.THUMB,Qt.AspectRatioMode.KeepAspectRatio,
                                                             Qt.TransformationMode.SmoothTransformation))
    def set_error(self,message):
        self._error=message
        self.setToolTip(f'⚠ {message}' if message else '')
        if not self.isSelected():self.setPen(QPen(QColor('#e0786c' if message else '#4a606c'),2 if message else 1))
    def itemChange(self,change,value):
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and hasattr(self,'owner'):
            self.data['x'],self.data['y']=value.x(),value.y();self.owner.update_edges()
        if change==QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            error=getattr(self,'_error',None)
            self.setPen(QPen(QColor('#83e5c6' if value else '#e0786c' if error else '#4a606c'),2 if value or error else 1))
        return super().itemChange(change,value)
    def mousePressEvent(self,event):
        self._start=QPointF(self.pos());super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self.pos()!=getattr(self,'_start',self.pos()):self.owner.creator.commit(render=False)


class GraphScene(QGraphicsScene):
    def __init__(self,creator):
        super().__init__();self.creator=creator;self.nodes={};self.cables=[];self._drag=None;self._wire=None;self.loading=False
        self.selectionChanged.connect(self.selected)
    def rebuild(self):
        self.loading=True;selected={n.nid for n in self.selectedItems() if isinstance(n,Node)}
        self.clear();self.nodes={};self.cables=[];self._drag=self._wire=None
        for data in self.creator.graph['nodes']:
            node=Node(self,data);self.addItem(node);self.nodes[node.nid]=node;node.setSelected(node.nid in selected)
        self.update_edges();self.loading=False
    def selected(self):
        if not self.loading:
            node=next((n for n in self.selectedItems() if isinstance(n,Node)),None)
            self.creator.inspect(node.data if node else None)
    def update_edges(self):
        if self.loading:return
        for item in self.cables:
            if item.scene() is self:self.removeItem(item)
        self.cables=[]
        for edge in self.creator.graph.get('edges',[]):
            a,b=self.nodes.get(edge['from']),self.nodes.get(edge['to'])
            if not a or not b or not a.output or edge.get('input',0)>=len(b.ports):continue
            item=QGraphicsPathItem(self.curve(a.output.scenePos(),b.ports[edge.get('input',0)].scenePos()))
            item.setPen(QPen(QColor('#d39b55' if a.output.kind=='field' else '#6eaaa4'),2.5));item.setZValue(-1);self.addItem(item);self.cables.append(item)
    @staticmethod
    def curve(a,b):
        p=QPainterPath(a);d=max(70,abs(b.x()-a.x())*.45);p.cubicTo(a+QPointF(d,0),b-QPointF(d,0),b);return p
    def mousePressEvent(self,event):
        item=self.itemAt(event.scenePos(),QTransform())
        if isinstance(item,Port):
            if item.output:
                self._drag=item;self._wire=QGraphicsPathItem();self._wire.setPen(QPen(QColor('#a5f3df'),2));self.addItem(self._wire)
            else:
                self.creator.graph['edges']=[e for e in self.creator.graph['edges'] if not(e['to']==item.node.nid and e.get('input',0)==item.index)]
                self.creator.commit();self.update_edges()
            event.accept();return
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self._wire and self._drag:self._wire.setPath(self.curve(self._drag.scenePos(),event.scenePos()));event.accept();return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._wire:
            self.removeItem(self._wire);self._wire=None
            target=next((p for p in self.items(event.scenePos()) if isinstance(p,Port) and not p.output),None)
            if target and self._drag and target.node.nid!=self._drag.node.nid:
                self.creator.connect_nodes(self._drag.node.nid,target.node.nid,target.index)
            self._drag=None;event.accept();return
        super().mouseReleaseEvent(event)
    def drawBackground(self,painter,rect):
        painter.fillRect(rect,QColor('#192228'));painter.setPen(QPen(QColor('#2b3941'),1))
        if rect.width()>6000:return
        for x in range(int(rect.left()/24)*24,int(rect.right())+24,24):
            for y in range(int(rect.top()/24)*24,int(rect.bottom())+24,24):painter.drawPoint(x,y)


class GraphView(QGraphicsView):
    def __init__(self,scene):
        super().__init__(scene);self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag);self.setMinimumWidth(320)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
    def wheelEvent(self,event):
        if event.modifiers()&Qt.KeyboardModifier.ControlModifier:
            factor=1.15 if event.angleDelta().y()>0 else 1/1.15
            if .15<self.transform().m11()*factor<3:self.scale(factor,factor)
            event.accept()
        else:super().wheelEvent(event)
    def keyPressEvent(self,event):
        creator=self.scene().creator;ctrl=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
        shift=bool(event.modifiers()&Qt.KeyboardModifier.ShiftModifier)
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace):creator.delete_nodes();event.accept()
        elif ctrl and event.key()==Qt.Key.Key_C:creator.copy_nodes();event.accept()
        elif ctrl and event.key()==Qt.Key.Key_V:creator.paste_nodes();event.accept()
        elif ctrl and event.key()==Qt.Key.Key_D:creator.duplicate_selected();event.accept()
        elif ctrl and shift and event.key()==Qt.Key.Key_G:creator.ungroup_selected();event.accept()
        elif ctrl and event.key()==Qt.Key.Key_G:creator.group_selected();event.accept()
        elif event.key()==Qt.Key.Key_F and not ctrl:self.frame_all();event.accept()
        else:super().keyPressEvent(event)
    def frame_all(self):
        self.fitInView(self.scene().itemsBoundingRect().adjusted(-55,-80,55,80),Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11()>1:self.resetTransform()


class RenderSignals(QObject):done=Signal(int,object,object,str,object)
class RenderJob(QRunnable):
    def __init__(self,graph,revision,thumbnails=True):
        super().__init__();self.graph=graph;self.revision=revision;self.thumbnails=thumbnails;self.signals=RenderSignals()
    def run(self):
        extra={'thumbs':{},'errors':{}}
        try:
            if self.thumbnails:
                values,errors=engine.all_values(self.graph);extra['errors']=errors
                background=self.graph.get('settings',{}).get('background','#24333b')
                for nid,value in values.items():
                    try:extra['thumbs'][nid]=engine.thumbnail(value,64,'#24333b' if background=='transparent' else background)
                    except Exception:pass
            shapes=engine.evaluate(self.graph)
            image=engine.render(self.graph,384,shapes=shapes);mask=engine.render(self.graph,384,mask=True,shapes=shapes)
            smooth=' · smooth raster' if self.graph.get('settings',{}).get('smooth') else ''
            self.signals.done.emit(self.revision,image,mask,f'{len(shapes):,} paths · procedural geometry{smooth}',extra)
        except Exception as exc:self.signals.done.emit(self.revision,None,None,str(exc),extra)


class PublishSignals(QObject):done=Signal(object,str)
class PublishJob(QRunnable):
    """Renders the texture for live wormhole links off the UI thread."""
    def __init__(self,graph,size):
        super().__init__();self.graph=graph;self.size=size;self.signals=PublishSignals()
    def run(self):
        try:self.signals.done.emit(engine.png_bytes(engine.render(self.graph,self.size)),'')
        except Exception as exc:self.signals.done.emit(None,str(exc))


class TextureCreator(QObject):
    changed=Signal()
    default_name='Procedural texture'
    def __init__(self,host):
        super().__init__();self.host=host;self.t=theme(host);self.graph=engine.preset();self.image=QImage();self.mask=QImage()
        self.show_repeat=True;self.show_mask=False;self._edit=None;self._test=None;self._previews=[];self._sync=False;self._revision=0
        self._pool=QThreadPool(self);self._pool.setMaxThreadCount(1);self._busy=False;self._pending=False;self._job=None;self._closed=False
        self._timer=QTimer(self);self._timer.setSingleShot(True);self._timer.setInterval(100);self._timer.timeout.connect(self._render)
        self._thumbs={};self._node_errors={};self._clipboard=None;self._wormhole=None;self._links={};self._publish_job=None
        self._publish_pool=QThreadPool(self);self._publish_pool.setMaxThreadCount(1)
        self._publish_timer=QTimer(self);self._publish_timer.setSingleShot(True);self._publish_timer.setInterval(500)
        self._publish_timer.timeout.connect(self._publish)
        self.history=History(self.snapshot,self._apply);self.history.reset();self._timer.start()
    def snapshot(self):return copy.deepcopy(self.graph)
    def load(self,data):
        if not data:return
        engine.validate(data);self._apply(data);self.history.reset()
    def _apply(self,data):
        self.graph=copy.deepcopy(data);self._revision+=1
        self.graph.setdefault('settings',{})
        for node in self.graph['nodes']:node.setdefault('params',{})
        if self._edit:
            self.scene.rebuild();self.scene.update_edges();self.inspect(None)
            self._sync=True;self.seamless.setChecked(self.graph['settings'].get('seamless',True));self.resolution.setValue(self.graph['settings'].get('resolution',1024))
            self.field_detail.setCurrentIndex(max(0,self.field_detail.findData(self.graph['settings'].get('field_resolution',256))))
            self.smooth.setChecked(self.graph['settings'].get('smooth',False));self._sync=False;self.refresh_quick()
        self._timer.start()
    def validate(self):
        try:engine.validate(self.graph);return []
        except Exception as exc:return [('error',str(exc))]
    def resource_payload(self):return {'type':'procedural_texture','graph':self.snapshot(),'seamless':self.graph['settings'].get('seamless',True),'formats':['svg','png','tiff','webp','brush'],'requires_images':False}
    def library_export(self,name):return 'textures',{'format':'ExistenceProceduralTexture','version':1,'name':name,'content':self.snapshot()},['stardust','nebula','ephemeris','atlas']
    def shutdown(self):
        self._closed=True;self._timer.stop();self._publish_timer.stop();self._pending=False
        self._pool.waitForDone();self._publish_pool.waitForDone()

    def library_files(self, name):
        size=min(self.graph['settings'].get('resolution',1024),4096)
        return [('textures', '.png', engine.png_bytes(engine.render(self.graph,size))),
                ('textures', '.svg', engine.svg(self.graph).encode('utf-8'))]

    def undo(self):
        if self.history.undo():self.changed.emit()
    def redo(self):
        if self.history.redo():self.changed.emit()
    def commit(self,render=True):
        if self._sync:return
        if self.history.commit():self.changed.emit()
        if render:self._revision+=1;self._timer.start()
    def _render(self):
        if self._closed:return
        if self._busy:self._pending=True;return
        self._busy=True;self._pending=False
        self._job=RenderJob(self.snapshot(),self._revision,self._edit is not None);self._job.signals.done.connect(self._rendered);self._pool.start(self._job)
    def _rendered(self,revision,image,mask,status,extra=None):
        self._busy=False
        if self._closed:return
        if revision==self._revision:
            self._apply_extra(extra or {})
            if image is not None:self.image,self.mask=image,mask;self._schedule_publish()
            if self._edit:self.status.setText(status);self.status.setStyleSheet('color:'+('#9ed8c6' if image is not None else '#ff9f91')+';padding:5px;')
            for preview in self._previews:preview.update()
        if self._pending or revision!=self._revision:self._timer.start(0)
    def connect_nodes(self,source,target,port=0):
        nodes={n['id']:n for n in self.graph['nodes']};kinds={k:n['type'] for k,n in nodes.items()}
        target_spec=engine.node_spec(nodes[target])
        given=engine.node_spec(nodes[source])['out'];expected=target_spec['ports'][port]
        if expected not in ('any',given):
            hint=(" — add a Contours node to turn a field into geometry" if given=='field' else
                  " — add a Rasterize node to turn geometry into a field")
            self.status.setText(f"{kinds[target]} · {target_spec['port_names'][port]} expects a {expected}; {kinds[source]} outputs a {given}{hint}")
            return False
        # Cycle check on partial graphs, allowing users to wire nodes in any order.
        edges=[e for e in self.graph['edges'] if not(e['to']==target and e.get('input',0)==port)]
        todo=[target];seen=set()
        while todo:
            n=todo.pop()
            if n==source:self.status.setText('Connection rejected: this would create a cycle');return False
            if n in seen:continue
            seen.add(n);todo.extend(e['to'] for e in edges if e['from']==n)
        edges.append({'from':source,'to':target,'input':port});self.graph['edges']=edges
        self.scene.update_edges();self.commit();return True
    def add_node(self):
        kind=self.node_choice.currentData()
        text=self.node_choice.currentText().strip().casefold()
        if not kind or (text and text not in self.node_choice.itemText(self.node_choice.currentIndex()).casefold()):
            match=next((self.node_choice.itemData(i) for i in range(self.node_choice.count())
                        if text and text in self.node_choice.itemText(i).casefold()),None)
            kind=match or kind
        if not kind:return
        data=engine.make_node(kind);data['id']=uuid.uuid4().hex[:8]
        center=self.view.mapToScene(self.view.viewport().rect().center());data['x'],data['y']=center.x()-80,center.y()-40
        if kind=='Output' and any(n['type']=='Output' for n in self.graph['nodes']):self.status.setText('The graph already has an Output');return
        self.graph['nodes'].append(data);self.scene.rebuild();self.scene.update_edges();self.scene.nodes[data['id']].setSelected(True);self.commit()
    def delete_nodes(self):
        ids={n.nid for n in self.scene.selectedItems() if isinstance(n,Node) and n.data['type']!='Output'}
        self.graph['nodes']=[n for n in self.graph['nodes'] if n['id'] not in ids]
        self.graph['edges']=[e for e in self.graph['edges'] if e['from'] not in ids and e['to'] not in ids]
        self.graph['exposed']=[e for e in self.graph.get('exposed',[]) if e.get('node') not in ids]
        self.scene.rebuild();self.scene.update_edges();self.inspect(None);self.refresh_quick();self.commit()
    def inspect(self,node):
        if not self._edit:return
        while self.form.rowCount():self.form.removeRow(0)
        self.inspector_title.setText((node.get('name') or node['type']) if node else 'Select a node to edit its settings')
        if not node:return
        error=self._node_errors.get(node['id'])
        if error:
            warning=QLabel(f'⚠ {error}');warning.setWordWrap(True);warning.setStyleSheet('color:#ff9f91;');self.form.addRow(warning)
        if engine.node_spec(node)['out']=='field':
            thumb=QLabel()
            try:
                image=engine.field_preview(self.graph,node['id'],144)
                if image is not None:thumb.setPixmap(QPixmap.fromImage(image));thumb.setToolTip('Field value (black 0 → white 1)')
            except Exception as exc:thumb.setText(f'Preview unavailable: {exc}');thumb.setWordWrap(True)
            self.form.addRow('Field',thumb)
        if node['type']=='Group':
            name=QLineEdit(node.get('name') or 'Group')
            name.editingFinished.connect(lambda nid=node['id'],w=name:self.rename_node(nid,w.text()))
            self.form.addRow('Name',name)
            inner=node['group']['graph']['nodes']
            info=QLabel(f"{len([n for n in inner if n['type'] not in ('Group input','Output')])} nodes inside · "
                        f"{len(node['group']['ports'])} input(s) → {node['group']['out']}. Ungroup (Ctrl+Shift+G) to edit its contents.")
            info.setWordWrap(True);info.setStyleSheet('color:#92a5af;');self.form.addRow(info)
            button=QPushButton('Ungroup');button.clicked.connect(self.ungroup_selected);self.form.addRow(button)
            return
        for key,spec in engine.SCHEMA[node['type']]['params'].items():
            row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
            layout.addWidget(self._param_widget(node,key,spec),1)
            star=QToolButton();star.setText('★' if self._is_exposed(node['id'],key) else '☆');star.setAutoRaise(True)
            star.setToolTip('Show this parameter in Quick controls')
            star.clicked.connect(lambda checked=False,nid=node['id'],k=key:self.toggle_expose(nid,k));layout.addWidget(star)
            self.form.addRow(spec[0],row)
    def rename_node(self,nid,name):
        node=next((n for n in self.graph['nodes'] if n['id']==nid),None)
        if node and name.strip() and node.get('name')!=name.strip():
            node['name']=name.strip();self.scene.rebuild();self.scene.update_edges();self.refresh_quick();self.commit(render=False)
    # ── node thumbnails / errors ──
    def _apply_extra(self,extra):
        self._thumbs=extra.get('thumbs',{}) or {};self._node_errors=extra.get('errors',{}) or {}
        if self._edit:
            for nid,item in self.scene.nodes.items():
                item.set_thumbnail(self._thumbs.get(nid));item.set_error(self._node_errors.get(nid))
    # ── parameter widgets, shared by the inspector and the quick controls ──
    def _param_widget(self,node,key,spec):
        value=node['params'].get(key,spec[2])
        if spec[1]=='number':
            widget=QDoubleSpinBox();widget.setRange(spec[3],spec[4]);widget.setDecimals(3 if spec[4]<=10 else 1)
            widget.setSingleStep(.05 if spec[4]<=10 else 1);widget.setValue(value)
            widget.valueChanged.connect(lambda value,nid=node['id'],k=key:self.set_parameter(nid,k,value))
        elif spec[1]=='choice':
            widget=QComboBox();widget.addItems(spec[3]);widget.setCurrentText(value)
            widget.currentTextChanged.connect(lambda value,nid=node['id'],k=key:self.set_parameter(nid,k,value))
        elif spec[1]=='file':
            widget=QPushButton(Path(value).name if value else 'Choose image…');widget.setToolTip(value or 'No image selected')
            widget.clicked.connect(lambda checked=False,nid=node['id'],k=key:self.pick_file(nid,k))
        else:
            widget=QPushButton(value);widget.setStyleSheet(f'border-left:18px solid {value};')
            widget.clicked.connect(lambda checked=False,nid=node['id'],k=key:self.pick_color(nid,k))
        return widget
    def _is_exposed(self,nid,key):
        return any(e.get('node')==nid and e.get('param')==key for e in self.graph.get('exposed',[]))
    def toggle_expose(self,nid,key):
        exposed=self.graph.setdefault('exposed',[])
        if self._is_exposed(nid,key):self.graph['exposed']=[e for e in exposed if not(e.get('node')==nid and e.get('param')==key)]
        else:exposed.append({'node':nid,'param':key})
        self.refresh_quick();self.commit(render=False)
        node=next((n for n in self.graph['nodes'] if n['id']==nid),None)
        if node:self.inspect(node)
    def refresh_quick(self):
        if not self._edit:return
        while self.quick_form.rowCount():self.quick_form.removeRow(0)
        controls=engine.exposed_controls(self.graph)
        self.quick_box.setVisible(bool(controls))
        for node,key,spec,label in controls:self.quick_form.addRow(label,self._param_widget(node,key,spec))
    def pick_file(self,nid,key):
        node=next(n for n in self.graph['nodes'] if n['id']==nid)
        path,_=QFileDialog.getOpenFileName(self._edit,'Image for the texture',node['params'].get(key,''),
                                           'Images (*.png *.jpg *.jpeg *.tif *.tiff *.webp *.bmp);;All files (*)')
        if path:self.set_parameter(nid,key,path);self.inspect(node)
    # ── clipboard, duplicate, groups ──
    def _selected_ids(self):
        return [n.nid for n in self.scene.selectedItems() if isinstance(n,Node) and n.data['type']!='Output']
    def copy_nodes(self):
        ids=set(self._selected_ids())
        if not ids:return
        nodes=[copy.deepcopy(n) for n in self.graph['nodes'] if n['id'] in ids]
        edges=[copy.deepcopy(e) for e in self.graph['edges'] if e['from'] in ids and e['to'] in ids]
        self._clipboard={'format':'ExistenceTextureNodes','version':1,'nodes':nodes,'edges':edges}
        QApplication.clipboard().setText(json.dumps(self._clipboard))
        self.status.setText(f'{len(nodes)} node(s) copied')
    def paste_nodes(self):
        data=None
        try:
            text=QApplication.clipboard().text();candidate=json.loads(text) if text.strip().startswith('{') else None
            if isinstance(candidate,dict) and candidate.get('format')=='ExistenceTextureNodes':data=candidate
        except ValueError:pass
        data=data or self._clipboard
        if not data:return
        temp={'nodes':data['nodes'],'edges':data['edges']}
        added,edges=engine.duplicate_nodes(temp,[n['id'] for n in data['nodes']],offset=60)
        self._insert(added,edges)
    def duplicate_selected(self):
        ids=self._selected_ids()
        if ids:
            added,edges=engine.duplicate_nodes(self.graph,ids);self._insert(added,edges)
    def _insert(self,added,edges):
        if not added:return
        trial=copy.deepcopy(self.graph);trial['nodes']+=added;trial['edges']+=edges
        try:engine.validate(trial,partial=True)
        except ValueError as exc:self.status.setText(f'Paste rejected: {exc}');return
        self.graph=trial;self.scene.rebuild();self.scene.update_edges();self.scene.clearSelection()
        for node in added:self.scene.nodes[node['id']].setSelected(True)
        self.commit()
    def group_selected(self):
        ids=self._selected_ids()
        if not ids:self.status.setText('Select the nodes to group');return
        name,ok=QInputDialog.getText(self._edit,'Group nodes','Group name:',text='Group')
        if not ok:return
        try:graph,gid=engine.group_nodes(self.graph,ids,name.strip() or 'Group')
        except ValueError as exc:self.status.setText(str(exc));return
        self.graph=graph;self.scene.rebuild();self.scene.update_edges();self.scene.nodes[gid].setSelected(True);self.commit()
    def ungroup_selected(self):
        groups=[n.nid for n in self.scene.selectedItems() if isinstance(n,Node) and n.data['type']=='Group']
        if not groups:self.status.setText('Select a group to ungroup');return
        graph=self.graph;restored=[]
        try:
            for gid in groups:graph,ids=engine.ungroup(graph,gid);restored+=ids
        except ValueError as exc:self.status.setText(str(exc));return
        self.graph=graph;self.scene.rebuild();self.scene.update_edges()
        for nid in restored:
            if nid in self.scene.nodes:self.scene.nodes[nid].setSelected(True)
        self.commit()
    # ── live wormhole link (Nebula, Nova, Ephemeris…) ──
    def _hole(self):
        if self._wormhole is None:
            try:
                from modules.wormhole import Wormhole
                self._wormhole=Wormhole(self.host.get('host_id') or 'stardust')
            except Exception:self._wormhole=False
        return self._wormhole or None
    def _refresh_destinations(self):
        hole=self._hole();self.link_target.clear()
        for app_id,name in (hole.destinations('image',live=True) if hole else []):self.link_target.addItem(name,app_id)
        self.link_button.setEnabled(self.link_target.count()>0)
        if not self.link_target.count():self.link_target.addItem('No live destination')
    def toggle_live_link(self):
        hole=self._hole();target=self.link_target.currentData()
        if not hole or not target:return
        if target in self._links:
            try:hole.unlink(self._links.pop(target))
            except Exception:self._links.pop(target,None)
            self.status.setText(f'Live link to {self.link_target.currentText()} closed')
        else:
            try:
                size=min(self.graph['settings'].get('resolution',1024),2048)
                message=hole.send(target,data=engine.png_bytes(engine.render(self.graph,size)),name='texture.png',
                                  kind='image',live=True,meta={'source':'texture_creator','seamless':self.graph['settings'].get('seamless',True)})
                self._links[target]=message['link']
                self.status.setText(f'Live link to {self.link_target.currentText()}: every change is sent automatically')
            except Exception as exc:QMessageBox.warning(self._edit,'Live link failed',str(exc));return
        self._update_link_button()
    def _update_link_button(self):
        if hasattr(self,'link_button'):
            linked=self.link_target.currentData() in self._links
            self.link_button.setText('Unlink' if linked else 'Link live')
    def _schedule_publish(self):
        if self._links and not self._closed:self._publish_timer.start()
    def _publish(self):
        if not self._links or self._closed:return
        size=min(self.graph['settings'].get('resolution',1024),2048)
        job=PublishJob(self.snapshot(),size);job.signals.done.connect(self._published);self._publish_job=job;self._publish_pool.start(job)
    def _published(self,data,error):
        hole=self._hole()
        if data is None or not hole:return
        for target,link in list(self._links.items()):
            try:hole.publish(link,data=data,name='texture.png')
            except KeyError:self._links.pop(target,None)
            except Exception:pass
        self._update_link_button()
    # ── PBR export ──
    def export_pbr(self):
        folder=QFileDialog.getExistingDirectory(self._edit,'Export PBR maps to folder')
        if not folder:return
        try:
            name,ok=QInputDialog.getText(self._edit,'PBR set','Material name:',text='texture')
            if not ok:return
            maps=engine.pbr_maps(self.graph,self.resolution.value())
            for channel,image in maps.items():
                path=Path(folder)/f'{name}_{channel}.png'
                if not image.save(str(path),'PNG'):raise ValueError(f'Cannot write {path.name}')
            self.status.setText(f'PBR set exported: {", ".join(maps)} → {folder}')
        except Exception as exc:QMessageBox.warning(self._edit,'PBR export failed',str(exc))
    def set_parameter(self,nid,key,value):
        node=next(n for n in self.graph['nodes'] if n['id']==nid);node['params'][key]=value;self.commit()
    def pick_color(self,nid,key):
        from PySide6.QtWidgets import QColorDialog
        node=next(n for n in self.graph['nodes'] if n['id']==nid);c=QColorDialog.getColor(QColor(node['params'][key]),self._edit)
        if c.isValid():self.set_parameter(nid,key,c.name());self.inspect(node)
    def change_preset(self,name):
        self._apply(engine.preset(name));self.commit();QTimer.singleShot(0,self.view.frame_all)
    def _setting(self,key,value):
        self.graph['settings'][key]=value;self.commit()
    def _background(self):
        from PySide6.QtWidgets import QColorDialog
        c=QColorDialog.getColor(QColor(self.graph['settings'].get('background','#24333b')),self._edit)
        if c.isValid():self._setting('background',c.name())
    def _preview_toggle(self):
        self.show_repeat=self.repeat.isChecked();self.show_mask=self.mask_button.isChecked()
        for preview in self._previews:preview.update()
    def edit_widget(self):
        if self._edit:return self._edit
        root=QWidget();self._edit=root;layout=QVBoxLayout(root);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        root.setStyleSheet('QSpinBox { background:#202b34; color:#e4edf0; border:1px solid #48565f; border-radius:4px; padding:5px; }')
        top=QHBoxLayout();presets=QComboBox();presets.addItems(engine.PRESETS);presets.setCurrentText('Terrazzo');presets.activated.connect(lambda i:self.change_preset(presets.itemText(i)))
        top.addWidget(QLabel('PRESET'));top.addWidget(presets)
        self.seamless=QCheckBox('Seamless');self.seamless.setChecked(self.graph['settings'].get('seamless',True));self.seamless.toggled.connect(lambda v:self._setting('seamless',v));top.addWidget(self.seamless)
        self.repeat=QCheckBox('3 × 3 proof');self.repeat.setChecked(True);self.repeat.toggled.connect(self._preview_toggle);top.addWidget(self.repeat)
        self.mask_button=QCheckBox('Brush mask');self.mask_button.toggled.connect(self._preview_toggle);top.addWidget(self.mask_button)
        top.addWidget(QLabel('FIELD DETAIL'));self.field_detail=QComboBox()
        for value in (128,256,512,1024):self.field_detail.addItem(f'{value} px',value)
        self.field_detail.setCurrentIndex(max(0,self.field_detail.findData(self.graph['settings'].get('field_resolution',256))))
        self.field_detail.setToolTip('Resolution of continuous fields (noise, fibres, cracks…). Higher is finer and slower.')
        self.field_detail.activated.connect(lambda i:self._setting('field_resolution',self.field_detail.itemData(i)));top.addWidget(self.field_detail)
        self.smooth=QCheckBox('Smooth raster');self.smooth.setChecked(self.graph['settings'].get('smooth',False))
        self.smooth.setToolTip('PNG / brush / preview use the continuous field instead of vector bands. SVG stays vector.')
        self.smooth.toggled.connect(lambda v:self._setting('smooth',v));top.addWidget(self.smooth)
        top.addStretch();layout.addLayout(top)
        row=QHBoxLayout();self.node_choice=QComboBox();self.node_choice.setEditable(True)
        self.node_choice.setInsertPolicy(QComboBox.InsertPolicy.NoInsert);self.node_choice.setMinimumWidth(260)
        for category in dict.fromkeys(v['category'] for v in engine.SCHEMA.values()):
            for kind,spec in engine.SCHEMA.items():
                if spec['category']==category and not spec.get('hidden'):self.node_choice.addItem(f'{category} / {kind}',kind)
        completer=self.node_choice.completer();completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.node_choice.lineEdit().setPlaceholderText('Search nodes…');self.node_choice.lineEdit().returnPressed.connect(self.add_node)
        row.addWidget(self.node_choice);button=QPushButton('+ Node');button.clicked.connect(self.add_node);row.addWidget(button)
        for label,slot,tip in (('Group',self.group_selected,'Pack the selected nodes into one node (Ctrl+G)'),
                               ('Ungroup',self.ungroup_selected,'Expand the selected group (Ctrl+Shift+G)')):
            button=QPushButton(label);button.setToolTip(tip);button.clicked.connect(slot);row.addWidget(button)
        button=QPushButton('Frame graph');button.clicked.connect(lambda:self.view.frame_all());row.addWidget(button)
        button=QPushButton('Background');button.clicked.connect(self._background);row.addWidget(button)
        button=QPushButton('Transparent');button.clicked.connect(lambda:self._setting('background','transparent'));row.addWidget(button);row.addStretch();layout.addLayout(row)
        self.scene=GraphScene(self);self.view=GraphView(self.scene);self.scene.rebuild();self.scene.update_edges()
        splitter=QSplitter();splitter.addWidget(self.view)
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(4,0,0,0)
        preview=Preview(self);preview.setMaximumHeight(350);self._previews.append(preview);right_layout.addWidget(preview,1)
        self.quick_box=QGroupBox('Quick controls');self.quick_form=QFormLayout(self.quick_box);right_layout.addWidget(self.quick_box)
        self.quick_box.setToolTip('Parameters starred (☆) in the inspector')
        self.inspector_title=QLabel('Select a node to edit its settings');right_layout.addWidget(self.inspector_title)
        scroller=QScrollArea();scroller.setWidgetResizable(True);scroller.setMinimumWidth(260);form_widget=QWidget();self.form=QFormLayout(form_widget);scroller.setWidget(form_widget);right_layout.addWidget(scroller,1)
        splitter.addWidget(right);splitter.setSizes([800,330]);layout.addWidget(splitter,1)
        hint=QLabel('Teal ports carry vector geometry, amber ports carry continuous fields (0–1). Hollow ports are optional. '
                    'Contours turns a field into vector shapes; Mask / Displace / Flow scatter let a field drive geometry. '
                    'Drag an output dot onto an input · Click an input to disconnect · Delete removes nodes · Ctrl+C / Ctrl+V / Ctrl+D copy, paste, duplicate · '
                    'Ctrl+G groups · ☆ adds a parameter to Quick controls · Ctrl+wheel zooms · F frames the graph')
        hint.setWordWrap(True);hint.setStyleSheet('color:#92a5af;font-size:11px;');layout.addWidget(hint)
        self.status=QLabel('Procedural geometry and fields. Image nodes can bring in a picture as a field.');self.status.setWordWrap(True);layout.addWidget(self.status)
        export=QHBoxLayout();self.resolution=QSpinBox();self.resolution.setRange(16,8192);self.resolution.setValue(self.graph['settings'].get('resolution',1024));self.resolution.setSuffix(' px');self.resolution.valueChanged.connect(lambda v:self._setting('resolution',v));export.addWidget(self.resolution)
        for label,slot in [('Export…',self.export),('PBR set…',self.export_pbr),('Save graph',self.save),('Open graph',self.open),('Brush tip',self.use_as_brush),('Brush grain',lambda:self.use_as_brush('grain')),('Publish brush',self.publish_brush)]:
            button=QPushButton(label);button.clicked.connect(slot);export.addWidget(button)
        layout.addLayout(export)
        live=QHBoxLayout();live.addWidget(QLabel('LIVE WORMHOLE'))
        self.link_target=QComboBox();self.link_target.setMinimumWidth(140);live.addWidget(self.link_target)
        self.link_button=QPushButton('Link live');self.link_button.setToolTip('Send the texture to the app and keep it updated on every change')
        self.link_button.clicked.connect(self.toggle_live_link);live.addWidget(self.link_button)
        refresh=QPushButton('↻');refresh.setToolTip('Refresh destinations');refresh.clicked.connect(self._refresh_destinations);live.addWidget(refresh)
        self.link_target.currentIndexChanged.connect(lambda *_:self._update_link_button());live.addStretch();layout.addLayout(live)
        self._refresh_destinations();self.refresh_quick()
        QTimer.singleShot(0,self.view.frame_all);self._timer.start(0)
        return root
    def test_widget(self):
        if self._test:return self._test
        root=QWidget();layout=QVBoxLayout(root);label=QLabel('Repeat proof and alpha mask use the same procedural geometry as exported files.');label.setWordWrap(True);layout.addWidget(label)
        preview=Preview(self);self._previews.append(preview);layout.addWidget(preview,1);self._test=root;return root
    def export(self):
        path,chosen=QFileDialog.getSaveFileName(self._edit,'Export procedural texture','texture.svg','SVG vector (*.svg);;PNG image (*.png);;TIFF image (*.tif);;WebP image (*.webp);;Brush alpha mask (*.mask.png);;Nebula brush (*.json);;'
            'Height map 16-bit (*.height.png);;Normal map OpenGL / Blender (*.normal.png);;Normal map DirectX (*.normal-dx.png)')
        if not path:return
        try:
            size=self.resolution.value()
            if chosen.startswith('SVG'):
                if not path.lower().endswith('.svg'):path+='.svg'
                Path(path).write_text(engine.svg(self.graph),encoding='utf-8')
            elif chosen.startswith('Height') or chosen.startswith('Normal'):
                suffix='.height.png' if chosen.startswith('Height') else '.normal-dx.png' if 'DirectX' in chosen else '.normal.png'
                if not path.lower().endswith('.png'):path+=suffix
                image=(engine.height_image(self.graph,size) if chosen.startswith('Height') else
                       engine.normal_image(self.graph,size,4.0,'directx' if 'DirectX' in chosen else 'opengl'))
                if not image.save(path,'PNG'):raise ValueError('PNG encoder unavailable')
            elif chosen.startswith('Nebula'):
                if not path.lower().endswith('.json'):path+='.json'
                Path(path).write_text(json.dumps(engine.brush_payload(self.graph,Path(path).stem,min(size,4096)),indent=2),encoding='utf-8')
            else:
                fmt='TIFF' if chosen.startswith('TIFF') else 'WEBP' if chosen.startswith('WebP') else 'PNG'
                ext={'TIFF':'.tif','WEBP':'.webp','PNG':'.png'}[fmt]
                if not path.lower().endswith(ext):path+=ext
                image=engine.render(self.graph,size,mask=chosen.startswith('Brush'))
                if not image.save(path,fmt):raise ValueError(f'{fmt} encoder unavailable')
            self.status.setText('Exported '+str(path))
        except Exception as exc:QMessageBox.warning(self._edit,'Export failed',str(exc))
    def save(self):
        path,_=QFileDialog.getSaveFileName(self._edit,'Save procedural graph','texture.cstx','Texture graph (*.cstx)')
        if path:
            try:engine.save_graph(self.graph,path if path.endswith('.cstx') else path+'.cstx')
            except Exception as exc:QMessageBox.warning(self._edit,'Save failed',str(exc))
    def open(self):
        path,_=QFileDialog.getOpenFileName(self._edit,'Open procedural graph','','Texture graph (*.cstx)')
        if path:
            try:self.load(engine.load_graph(path));self.changed.emit();self.view.frame_all()
            except Exception as exc:QMessageBox.warning(self._edit,'Open failed',str(exc))
    def use_as_brush(self, role='tip'):
        if not isinstance(role,str):role='tip'
        callback=self.host.get('use_texture_as_brush')
        if callable(callback):
            try:callback(self.snapshot(),role)
            except Exception as exc:QMessageBox.warning(self._edit,'Brush conversion failed',str(exc))
        else:self.publish_brush()
    def publish_brush(self):
        try:
            from modules.resource_center.library import SharedLibrary
            payload=engine.brush_payload(self.graph,'Procedural texture',min(self.graph['settings'].get('resolution',512),4096))
            entry=SharedLibrary().add_json('brushes','Procedural texture',payload,apps=['nebula','stardust'],owner='stardust',suffix='.json')
            self.status.setText('Brush published to Existence Resources · available in Nebula')
        except Exception as exc:QMessageBox.warning(self._edit,'Publication failed',str(exc))
