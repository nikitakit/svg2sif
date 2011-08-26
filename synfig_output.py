#!/usr/bin/env python
"""
synfig_output.py
An Inkscape extension for exporting Synfig files (.sif)

Copyright (C) 2011 Nikita Kitaev

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""
import math

import inkex
from synfig_prepare import *
import synfig_fileformat as sif

###### Utility Classes ####################################

class SynfigDocument():
    """A synfig document, with commands for adding layers and layer parameters"""
    def __init__(self, width=1024, height=768, name="Synfig Animation 1"):
        self.guid=0
        self.root_canvas = etree.fromstring(
            """
<canvas
version="0.5"
width="%f"
height="%f"
xres="2834.645752"
yres="2834.645752"
view-box="0 0 0 0"
>
  <name>%s</name>
</canvas>
"""                % (width, height, name)
            )

        self._update_viewbox()

        self.gradients={}

    ### Properties

    def get_root_canvas(self):
        return self.root_canvas

    def get_root_tree(self):
        return self.root_canvas.getroottree()

    def _update_viewbox(self):
        attr_viewbox="%f %f %f %f" % (
             -self.width/2.0/sif.kux,
              self.height/2.0/sif.kux,
              self.width/2.0/sif.kux,
             -self.height/2.0/sif.kux
             )
        self.root_canvas.set("view-box",attr_viewbox)

    def get_width(self):
        return float(self.root_canvas.get("width","0"))

    def set_width(self, value):
        self.root_canvas.set("width", str(value))
        self._update_viewbox()

    def get_height(self):
        return float(self.root_canvas.get("height","0"))

    def set_height(self, value):
        self.root_canvas.set("height", str(value))
        self._update_viewbox()

    def get_name(self):
        return self.root_canvas.get("name","")

    def set_name(self, value):
        self.root_canvas.set("name", value)
        self._update_viewbox()

    width=property(get_width, set_width)
    height=property(get_height, set_height)
    name=property(get_name, set_name)

    ### Public utility functions
    def new_guid(self):
        self.guid+=1
        return str(self.guid)

    def distance_svg2sif(self,distance):
        return distance/sif.kux

    def distance_sif2svg(self,distance):
        return distance*sif.kux

    def coor_svg2sif(self,vector):
        x = vector[0]
        y = self.height - vector[1]

        x-=self.width/2.0
        y-=self.height/2.0
        x/=sif.kux
        y/=sif.kux

        return [x,y]

    def coor_sif2svg(self,vector):
        x=vector[0] * sif.kux + self.width/2.0
        y=vector[1] * sif.kux + self.height/2.0

        y=self.height - y

        if coor_svg2sif([x,y]) != vector:
            raise AssertionError, "sif to svg coordinate conversion error"

        return [x,y]

    def list_coor_svg2sif(self, l):
        # If list has two numerical elements,
        # treat it as a coordinate pair
        if type(l) == list and len(l) == 2:
            if type(l[0]) == int or type(l[0]) == float:
                if type(l[1]) == int or type(l[1]) == float:
                    l_sif=self.coor_svg2sif(l)
                    l[0]=l_sif[0]
                    l[1]=l_sif[1]
                    return

        # Otherwise recursively iterate over the list
        for x in l:
            if type(x) == list:
                self.list_coor_svg2sif(x)

    def list_coor_sif2svg(self, l):
        # If list has two numerical elements,
        # treat it as a coordinate pair
        if type(l) == list and len(l) == 2:
            if type(l[0]) == int or type(l[0]) == float:
                if type(l[1]) == int or type(l[1]) == float:
                    l_sif=self.coor_sif2svg(l)
                    l[0]=l_sif[0]
                    l[1]=l_sif[1]
                    return

        # Otherwise recursively iterate over the list
        for x in l:
            if type(x) == list:
                self.list_coor_sif2svg(x)

    def bline_coor_svg2sif(self,b):
        self.list_coor_svg2sif(b["points"])

    def bline_coor_sif2svg(self,b):
        self.list_coor_sif2svg(b["points"])

    ### XML Builders -- private

    def build_layer(self,layer_type,desc,canvas=None,active=True,version="auto"):
        """Build an empty layer"""
        if canvas is None:
            layer=self.root_canvas.makeelement("layer")
        else:
            layer=etree.SubElement(canvas,"layer")

        layer.set("type",layer_type)
        layer.set("desc",desc)
        if active:
            layer.set("active","true")
        else:
            layer.set("active","false")

        if version=="auto":
            version=sif.defaultLayerVersion(layer_type)

        if type(version) == float:
            version=str(version)

        layer.set("version",version)

        return layer


    def _calc_radius(self, p1x, p1y, p2x, p2y):
        # Synfig tangents are scaled by a factor of 3
        return 3.0 * math.sqrt( (p2x-p1x)**2 + (p2y-p1y)**2 )

    def _calc_angle(self, p1x, p1y, p2x, p2y):
        dx=p2x-p1x
        dy=p2y-p1y
        if dx>0 and dy>0:
            ag=math.pi + math.atan(dy/dx)
        elif dx>0 and dy<0:
            ag=math.pi + math.atan(dy/dx)
        elif dx<0 and dy<0:
            ag=math.atan(dy/dx)
        elif dx<0 and dy>0:
            ag=2*math.pi + math.atan(dy/dx)
        elif dx==0 and dy>0:
            ag=-1*math.pi/2
        elif dx==0 and dy<0:
            ag=math.pi/2
        elif dx==0 and dy==0:
            ag=0
        elif dx<0 and dy==0:
            ag=0
        elif dx>0 and dy==0:
            ag=math.pi

        return (ag*180)/math.pi

    def build_param(self,layer,name,value,param_type="auto", guid=None):
        """Add a parameter to a layer"""
        if layer is None:
            param=self.root_canvas.makeelement("param")
        else:
            param=etree.SubElement(layer,"param")
        param.set("name",name)

        #Automatically detect param_type
        if param_type=="auto":
            if layer is not None:
                layer_type=layer.get("type")
                param_type=sif.paramType(layer_type,name)
            else:
                param_type=sif.paramType(None,name,value)

        if param_type=="real":
            el=etree.SubElement(param,"real")
            el.set("value",str(float(value)))
        elif param_type=="integer":
            el=etree.SubElement(param,"integer")
            el.set("value",str(int(value)))
        elif param_type=="vector":
            el=etree.SubElement(param,"vector")
            x=etree.SubElement(el,"x")
            x.text=str(float(value[0]))
            y=etree.SubElement(el,"y")
            y.text=str(float(value[1]))
        elif param_type=="color":
            el=etree.SubElement(param,"color")
            r=etree.SubElement(el,"r")
            r.text=str(float(value[0]))
            g=etree.SubElement(el,"g")
            g.text=str(float(value[1]))
            b=etree.SubElement(el,"b")
            b.text=str(float(value[2]))
            a=etree.SubElement(el,"a")
            a.text=str(float(value[3])) if len(value)>3 else "1.0"
        elif param_type=="gradient":
            el=etree.SubElement(param,"gradient")
            # Value is a dictionary of color stops
            #  see get_gradient()
            for pos in value.keys():
                color=etree.SubElement(el, "color")
                color.set("pos", str(float(pos)))

                c=value[pos]

                r=etree.SubElement(color,"r")
                r.text=str(float(c[0]))
                g=etree.SubElement(color,"g")
                g.text=str(float(c[1]))
                b=etree.SubElement(color,"b")
                b.text=str(float(c[2]))
                a=etree.SubElement(color,"a")
                a.text=str(float(c[3])) if len(c)>3 else "1.0"
        elif param_type=="bool":
            el=etree.SubElement(param,"bool")
            if value:
                el.set("value","true")
            else:
                el.set("value","false")
        elif param_type=="time":
            el=etree.SubElement(param,"time")
            if type(value) == int:
                el.set("value", "%ds" % value)
            elif type(value) == float:
                el.set("value", "%fs" % value)
            elif type(value) == str:
                el.set("value", value)
        elif param_type=="bline":
            el=etree.SubElement(param,"bline")
            el.set("type","bline_point")

            # value is a bline (dictionary type), see path_to_bline_list
            if value["loop"] == True:
                el.set("loop","true")
            else:
                el.set("loop","false")

            for vertex in value["points"]:
                x=float(vertex[1][0])
                y=float(vertex[1][1])

                tg1x=float(vertex[0][0])
                tg1y=float(vertex[0][1])

                tg2x=float(vertex[2][0])
                tg2y=float(vertex[2][1])

                tg1_radius=self._calc_radius(x,y,tg1x,tg1y)
                tg1_angle=self._calc_angle(x,y,tg1x,tg1y)

                tg2_radius=self._calc_radius(x,y,tg2x,tg2y)
                tg2_angle=self._calc_angle(x,y,tg2x,tg2y)-180.0

                if vertex[3]:
                    split="true"
                else:
                    split="false"

                entry=etree.SubElement(el,"entry")
                composite=etree.SubElement(entry,"composite")
                composite.set("type","bline_point")

                point=etree.SubElement(composite,"point")
                vector=etree.SubElement(point,"vector")
                etree.SubElement(vector,"x").text=str(x)
                etree.SubElement(vector,"y").text=str(y)
                
                width=etree.SubElement(composite,"width")
                etree.SubElement(width,"real").set("value","1.0")

                origin=etree.SubElement(composite,"origin")
                etree.SubElement(origin,"real").set("value","0.5")

                split_el=etree.SubElement(composite,"split")
                etree.SubElement(split_el,"bool").set("value",split)

                t1=etree.SubElement(composite,"t1")
                t2=etree.SubElement(composite,"t2")

                t1_rc=etree.SubElement(t1,"radial_composite")
                t1_rc.set("type","vector")

                t2_rc=etree.SubElement(t2,"radial_composite")
                t2_rc.set("type","vector")

                t1_r=etree.SubElement(t1_rc,"radius")
                t2_r=etree.SubElement(t2_rc,"radius")
                t1_radius=etree.SubElement(t1_r,"real")
                t2_radius=etree.SubElement(t2_r,"real")
                t1_radius.set("value",str(tg1_radius))
                t2_radius.set("value",str(tg2_radius))

                t1_t=etree.SubElement(t1_rc,"theta")
                t2_t=etree.SubElement(t2_rc,"theta")
                t1_angle=etree.SubElement(t1_t,"angle")
                t2_angle=etree.SubElement(t2_t,"angle")
                t1_angle.set("value",str(tg1_angle))
                t2_angle.set("value",str(tg2_angle))
        elif param_type=="canvas":
            el=etree.SubElement(param,"canvas")
            el.set("xres","10.0")
            el.set("yres","10.0")

            # "value" is a list of layers
            if value is not None:
                for layer in value:
                    el.append(layer)
        else:
            raise AssertionError, "Unsupported param type %s" % (param_type)
                
        # TODO: set guid of "el"

        return param

    ### Public layer API

    def create_layer(self,layer_type,desc,params={},guids={},canvas=None,active=True,version="auto"):
        layer = self.build_layer(layer_type,desc,canvas,active,version)
        default_layer_params=sif.defaultLayerParams(layer_type)

        for param_name in default_layer_params.keys():
            param_type=default_layer_params[param_name][0]
            if param_name in params.keys():
                param_value=params[param_name]
            else:
                param_value=default_layer_params[param_name][1]

            if param_name in guids.keys():
                param_guid=guids[param_name]
            else:
                param_guid=None

            if param_value is not None:
                self.build_param(layer,param_name,param_value,param_type,guid=param_guid)

        return layer

    def set_param(self,layer,name,value,param_type="auto",guid=None,modify_linked=False):
        if modify_linked:
            raise AssertionError, "Modifying linked parameters is not supported"

        layer_type=layer.get("type")
        assert(layer_type)

        if param_type=="auto":
            param_type=sif.paramType(layer_type,name)

        # Remove existing parameters with this name
        existing=[]
        for param in layer.iterchildren():
            if param.get("name") == name:
                existing.append(param)

        if len(existing) == 0:
            self.build_param(layer,name,value,param_type,guid)
        elif len(existing) > 1:
            raise AssertionError, "Found multiple parameters with the same name"
        else:
            new_param = self.build_param(None,name,value,param_type,guid)
            layer.replace(existing[0], new_param)

    def set_params(self,layer,params={},guids={},modify_linked=False):
        for param_name in params.keys():
            if param_name in guids.keys():
                self.set_param(layer,param_name,params[param_name],guid=guids[param_name],modify_linked=modify_linked)
            else:
                self.set_param(layer,param_name,params[param_name],modify_linked=modify_linked)

    ### Public operations API
    # Operations act on a series of layers, and (optionally) on a series of named parameters
    # The "is_end" attribute should be set to true when the layers are at the end of a canvas
    # (i.e. when adding transform layers on top of them does not require encapsulation)

    def op_encapsulate(self, layers, name="Inline Canvas", is_end=False):
        if layers==[]:
            return layers

        layer=self.create_layer("PasteCanvas",name,params={"canvas":layers})
        return [layer]

    def op_color(self, layers, overlay, is_end=False):
        if layers==[]:
            return layers
        if overlay is None:
            return layers

        overlay_enc=self.op_encapsulate([overlay])
        self.set_param(overlay_enc[0],"blend_method", 21) # straight onto
        ret = layers + overlay_enc

        if is_end:
            return ret
        else:
            return self.op_encapsulate(ret)        

    def op_transform(self, layers, mtx, name="Transform", is_end=False):
        if layers==[]:
            return layers
        if mtx is None or mtx == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]:
            return layers

        src_tl=[100,100]
        src_br=[200,200]

        dest_tl=[100,100]
        dest_tr=[200,100]
        dest_br=[200,200]
        dest_bl=[100,200]

        simpletransform.applyTransformToPoint(mtx, dest_tl)
        simpletransform.applyTransformToPoint(mtx, dest_tr)
        simpletransform.applyTransformToPoint(mtx, dest_br)
        simpletransform.applyTransformToPoint(mtx, dest_bl)

        warp = self.create_layer("warp", name, params={
            "src_tl": self.coor_svg2sif(src_tl),
            "src_br": self.coor_svg2sif(src_br),
            "dest_tl": self.coor_svg2sif(dest_tl),
            "dest_tr": self.coor_svg2sif(dest_tr),
            "dest_br": self.coor_svg2sif(dest_br),
            "dest_bl": self.coor_svg2sif(dest_bl)
            } )

        if is_end:
            return layers + [warp]
        else:
            return self.op_encapsulate(layers + [warp])

    ### Global defs, and related
    ###  SVG Gradients
    def add_linear_gradient(self, gradient_id, p1, p2, mtx=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], stops=[], link=""):
        gradient = {
            "type"      : "linear",
            "p1"        : p1,
            "p2"        : p2,
            "mtx"       : mtx
            }
        if stops!=[]:
            gradient["stops"] = stops
            gradient["stops_guid"] = self.new_guid()
        elif link!="":
            gradient["link"] = link
        else:
            raise AssertionError, "Gradient has neither stops nor link"
        self.gradients[gradient_id] = gradient

    def add_radial_gradient(self, gradient_id, center, radius, focus, mtx=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], stops=[], link=""):
        gradient = {
            "type"      : "radial",
            "center"    : center,
            "radius"    : radius,
            "focus"     : focus,
            "mtx"       : mtx
            }
        if stops!=[]:
            gradient["stops"] = stops
            gradient["stops_guid"] = self.new_guid()
        elif link!="":
            gradient["link"] = link
        else:
            raise AssertionError, "Gradient has neither stops nor link"
        self.gradients[gradient_id] = gradient

    def get_gradient(self, gradient_id):
        """
        Returns a gradient with a given id

        Linear gradient format:
        {
        "type"      : "linear",
        "p1"        : [x, y],
        "p2"        : [x, y],
        "mtx"       : mtx,
        "stops"     : color stops,
        "stops_guid": color stops guid
        }

        Radial gradient format:
        {
        "type"      : "radial",
        "center"    : [x, y],
        "radius"    : r,
        "focus"     : [x, y],
        "mtx"       : mtx,
        "stops"     : color stops,
        "stops_guid": color stops guid
        }

        Color stops format
        {
        0.0         : color ([r,g,b,a] or [r,g,b]) at start,
        [a number]  : color at that position,
        1.0         : color at end
        }
        """

        if gradient_id not in self.gradients.keys():
            return None

        gradient = self.gradients[gradient_id]

        # If the gradient has no link, we are done
        if "link" not in gradient.keys() or gradient["link"] == "":
            return gradient

        # If the gradient does have a link, find the color stops recursively
        if gradient["link"] not in self.gradients.keys():
            raise AssertionError, "Linked gradient ID not found"

        linked_gradient = self.get_gradient(gradient["link"])
        gradient["stops"] = linked_gradient["stops"]
        gradient["stops_guid"] = linked_gradient["stops_guid"]
        del gradient["link"]

        # Update the gradient in our listing
        # (so recursive lookup only happens once)
        self.gradients[gradient_id] = gradient

        return gradient


###### Utility Functions ##################################

### Path related

def path_to_bline_list(path_d,nodetypes=None,mtx=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):
    """
    Converts a path to a BLine List

    bline_list format:

    Vertex:
    [[tg1x, tg1y], [x,y], [tg2x, tg2y], split = T/F]
    Vertex list:
    [ vertex, vertex, vertex, ...]
    Bline:
    {
    "points"    : vertex_list,
    "loop"      : True / False
    }
    """

    # Parse the path
    path=simplepath.parsePath(path_d)

    # Append (more than) enough c's to the nodetypes
    if nodetypes is None:
        nt = ""
    else:
        nt = nodetypes

    for _ in range(len(path)):
        nt+="c"

    # Create bline list
    #     borrows code from cubicsuperpath.py

    # bline_list := [bline, bline, ...]
    # bline := {
    #           "points":[vertex, vertex, ...],
    #           "loop":True/False,
    #          }

    bline_list=[]

    subpathstart = []
    last = []
    lastctrl = []
    lastsplit=True
    for s in path:
        cmd, params = s
        if cmd!="M" and bline_list==[]:
            raise AssertionError, "Bad path data: path doesn't start with moveto, %s, %s" % (s, path)
        elif cmd=="M":
            # Add previous point to subpath
            if last:
                bline_list[-1]["points"].append([lastctrl[:],last[:],last[:], lastsplit])
            # Start a new subpath
            bline_list.append({"nodetypes":"", "loop":False,"points":[]})
            # Save coordinates of this point
            subpathstart =  params[:]
            last=params[:]
            lastctrl = params[:]
            lastsplit = False if nt[0]=="z" else True
            nt=nt[1:]
        elif cmd == 'L':
            bline_list[-1]["points"].append([lastctrl[:],last[:],last[:], lastsplit])
            last = params[:]
            lastctrl = params[:]
            lastsplit = False if nt[0]=="z" else True
            nt=nt[1:]
        elif cmd == 'C':
            bline_list[-1]["points"].append([lastctrl[:],last[:],params[:2], lastsplit])
            last = params[-2:]
            lastctrl = params[2:4]
            lastsplit = False if nt[0]=="z" else True
            nt=nt[1:]
        elif cmd == 'Q':
            q0=last[:]
            q1=params[0:2]
            q2=params[2:4]
            x0=     q0[0]
            x1=1./3*q0[0]+2./3*q1[0]
            x2=           2./3*q1[0]+1./3*q2[0]
            x3=                           q2[0]
            y0=     q0[1]
            y1=1./3*q0[1]+2./3*q1[1]
            y2=           2./3*q1[1]+1./3*q2[1]
            y3=                           q2[1]
            bline_list[-1]["points"].append([lastctrl[:],[x0,y0],[x1,y1], lastsplit])
            last = [x3,y3]
            lastctrl = [x2,y2]
            lastsplit = False if nt[0]=="z" else True
            nt=nt[1:]
        elif cmd == 'A':
            arcp=cubicsuperpath.ArcToPath(last[:],params[:])
            arcp[ 0][0]=lastctrl[:]
            last=arcp[-1][1]
            lastctrl = arcp[-1][0]
            lastsplit = False if nt[0]=="z" else True
            nt=nt[1:]
            for el in arcp[:-1]:
                el.append(True)
                bline_list[-1]["points"].append(el)
        elif cmd=="Z":
            if len(bline_list[-1]["points"]) == 0:
                # If the path "loops" after only one point
                #  e.g. "M 0 0 Z"
                bline_list[-1]["points"].append([lastctrl[:],last[:],last[:], False])
            elif last==subpathstart:
                # If we are back to the original position
                # merge our tangent into the first point
                bline_list[-1]["points"][0][0]=lastctrl[:]
            else:
                # Otherwise draw a line to the starting point
                bline_list[-1]["points"].append([lastctrl[:],last[:],last[:], lastsplit])

            # Clear the variables (no more points need to be added)
            last=[]
            lastctrl=[]
            lastsplit=True

            # Loop the subpath
            bline_list[-1]["loop"] = True

            
    # Append final superpoint, if needed
    if last:
        bline_list[-1]["points"].append([lastctrl[:],last[:],last[:], lastsplit])

    # Apply the transformation
    if mtx != [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]:
        for bline in bline_list:
            for vertex in bline["points"]:
                for pt in vertex:
                    if type(pt) != bool:
                        simpletransform.applyTransformToPoint(mtx,pt)

    return bline_list

### Style related

def get_dimension(s="1024"):
    if s == "":
        return 0
    try:
        last=int(s[-1])
    except:
        last=None

    if type(last) == int:
        return float(s)
    elif s[-1]=="%":
        return 1024
    elif s[-2:]=="px":
        return float(s[:-2])
    elif s[-2:]=="pt":
        return float(s[:-2])*1.25
    elif s[-2:]=="em":
        return float(s[:-2])*16
    elif s[-2:]=="mm":
        return float(s[:-2])*3.54
    elif s[-2:]=="pc":
        return float(s[:-2])*15
    elif s[-2:]=="cm":
        return float(s[:-2])*35.43
    elif s[-2:]=="in":
        return float(s[:-2])*90
    else:
        return 1024

def extract_color(style, color_attrib, *opacity_attribs):
    if color_attrib in style.keys():
        c = simplestyle.parseColor(style[color_attrib])
    else:
        c = (0,0,0)

    # Convert color scales and adjust gamma
    color = [pow(c[0]/255.0,sif.gamma), pow(c[1]/255.0,sif.gamma), pow(c[2]/255.0,sif.gamma), 1.0]

    for opacity in opacity_attribs:
        if opacity in style.keys():
            color[3] = color[3] * float(style[opacity])
    return color

def extract_width(style, width_attrib, mtx):
    if width_attrib in style.keys():
        width = get_dimension(style[width_attrib])
    else:
        return 0

    # Calculate average scale factor
    area_scale_factor = mtx[0][0]*mtx[1][1] - mtx[0][1]*mtx[1][0]
    linear_scale_factor = math.sqrt(abs(area_scale_factor))

    return width*linear_scale_factor/sif.kux
    

###### Main Class #########################################
class SynfigExport(SynfigPrep):
    def __init__(self):
        SynfigPrep.__init__(self)

    def effect(self):
        # Prepare the document for exporting
        SynfigPrep.effect(self)

        svg = self.document.getroot()
        width = get_dimension(svg.get("width",1024))
        height = get_dimension(svg.get("height",768))

        title=svg.xpath("svg:title",namespaces=NSS)
        if len(title) == 1:
            name = title[0].text
        else:
            name = svg.get(addNS("docname","sodipodi"),"Synfig Animation 1")

        d = SynfigDocument(width, height, name)

        layers=[]
        for node in svg.iterchildren():
            layers+=self.convert_node(node,d)

        root_canvas=d.get_root_canvas()
        for layer in layers:
            root_canvas.append(layer)

        d.get_root_tree().write(sys.stdout)

    def convert_node(self,node,d):
        if node.tag == addNS("namedview","sodipodi"):
            return []
        elif node.tag == addNS("defs","svg"):
            self.parse_defs(node,d)
            return [] # Defs don't draw any layers
        elif node.tag == addNS("metadata","svg"):
            return []
        elif node.tag == addNS("g","svg"):
            layers = []
            for subnode in node:
                layers+=self.convert_node(subnode,d)

            if node.get(addNS("groupmode","inkscape")) != "layer":
                return layers
            else:
                name = node.get(addNS("label","inkscape"),"Inline Canvas")
                return d.op_encapsulate(layers, name=name)
        elif node.tag == addNS("path","svg"):
            return self.convert_path(node,d)
        else:
            # An unsupported element
            return []

    def parse_defs(self, node, d):        
        for child in node.iterchildren():
            if child.tag == addNS("linearGradient","svg"):
                gradient_id = child.get("id",str(id(child)))
                x1 = float(child.get("x1","0.0"))
                x2 = float(child.get("x2","0.0"))
                y1 = float(child.get("y1","0.0"))
                y2 = float(child.get("y2","0.0"))

                mtx = simpletransform.parseTransform(child.get("gradientTransform"))

                link = child.get(addNS("href", "xlink"), "#")[1:]
                if link == "":
                    stops = self.parse_stops(child, d)
                    d.add_linear_gradient(gradient_id, [x1, y1], [x2, y2], mtx, stops=stops)
                else:
                    d.add_linear_gradient(gradient_id, [x1, y1], [x2, y2], mtx, link=link)
            elif child.tag == addNS("radialGradient","svg"):
                gradient_id = child.get("id",str(id(child)))
                cx = float(child.get("cx","0.0"))
                cy = float(child.get("cy","0.0"))
                r  = float(child.get("r","0.0"))
                fx = float(child.get("fx","0.0"))
                fy = float(child.get("fy","0.0"))

                mtx = simpletransform.parseTransform(child.get("gradientTransform"))

                link = child.get(addNS("href", "xlink"), "#")[1:]
                if link == "":
                    stops = self.parse_stops(child, d)
                    d.add_radial_gradient(gradient_id, [cx, cy], r, [fx, fy], mtx, stops=stops)
                else:
                    d.add_radial_gradient(gradient_id, [cx, cy], r, [fx, fy], mtx, link=link)

    def parse_stops(self, node, d):
        stops = {}
        for stop in node.iterchildren():
            if stop.tag == addNS("stop", "svg"):
                offset = float(stop.get("offset"))
                style=simplestyle.parseStyle(stop.get("style",""))
                stops[offset] = extract_color(style, "stop-color", "stop-opacity")
            else:
                raise Exception, "Child of gradient is not a stop"

        return stops

    def convert_path(self, node, d):
        layers = []

        node_id = node.get("id",str(id(node)))
        style=simplestyle.parseStyle(node.get("style",""))
        mtx = simpletransform.parseTransform(node.get("transform"))

        blines = path_to_bline_list(node.get("d"),node.get(addNS("nodetypes","sodipodi")),mtx)
        for bline in blines:
            d.bline_coor_svg2sif(bline)

            if style.setdefault("fill", "none")  != "none":
                if style["fill"].startswith("url"):
                    # Gradient or pattern
                    # Draw the shape in black, then overlay it with the gradient or pattern
                    color = [0,0,0,1]
                else:
                    color = extract_color(style, "fill", "fill-opacity", "opacity")

                layer=d.create_layer("region",node_id,{
                        "bline": bline,
                        "color": color,
                        "winding_style": 1 if style.setdefault("fill-rule","evenodd")=="evenodd" else 0
                        }   )

                if style["fill"].startswith("url"):
                    color_layer=self.convert_url(style["fill"][5:-1],mtx,d)[0]
                    layer = d.op_color([layer],overlay=color_layer)[0]

                layers.append(layer)

            if style.setdefault("stroke", "none")  != "none":
                if style["stroke"].startswith("url"):
                    # Gradient or pattern
                    # Draw the shape in black, then overlay it with the gradient or pattern
                    color = [0,0,0,1]
                else:
                    color = extract_color(style, "stroke", "stroke-opacity", "opacity")

                layer=d.create_layer("outline",node_id,{
                        "bline": bline,
                        "color": color,
                        "width": extract_width(style,"stroke-width",mtx),
                        "sharp_cusps": True if style.setdefault("stroke-linejoin","miter")=="miter" else False,
                        "round_tip[0]": False if style.setdefault("stroke-linecap","butt")=="butt" else True,
                        "round_tip[1]": False if style.setdefault("stroke-linecap","butt")=="butt" else True
                        }   )

                if style["stroke"].startswith("url"):
                    color_layer=self.convert_url(style["stroke"][5:-1],mtx,d)[0]
                    layer = d.op_color([layer],overlay=color_layer)[0]

                layers.append(layer)

        return layers

    def convert_url(self,url_id,mtx,d):
        gradient = d.get_gradient(url_id)
        if gradient is None:
            # Patterns and other URLs not supported
            return [None]

        if gradient["type"] == "linear":
            layer=d.create_layer("linear_gradient",url_id,{
                    "p1" : d.coor_svg2sif(gradient["p1"]),
                    "p2" : d.coor_svg2sif(gradient["p2"]),
                    "gradient" : gradient["stops"],
                    },  guids={"gradient" : gradient["stops_guid"]}  )

        if gradient["type"] == "radial":
            layer=d.create_layer("radial_gradient",url_id,{
                    "center" : d.coor_svg2sif(gradient["center"]),
                    "radius" : d.distance_svg2sif(gradient["radius"]),
                    "gradient" : gradient["stops"],
                    },  guids={"gradient" : gradient["stops_guid"]}  )

        return d.op_transform([layer], simpletransform.composeTransform(mtx, gradient["mtx"]))


if __name__ == '__main__':
    e = SynfigExport()
    e.affect(output=False)


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
