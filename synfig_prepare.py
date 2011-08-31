#!/usr/bin/env python
"""
synfig_prepare.py
Simplifies SVG files in preparation for sif export.

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

import os, sys, tempfile

import inkex
from inkex import NSS, addNS, etree, debug, errormsg
import simplepath, simplestyle, simpletransform
import cubicsuperpath

###### Utility Classes ####################################

try:
    from subprocess import Popen, PIPE
    bsubprocess = True
except:
    bsubprocess = False

class InkscapeActionGroup:
    """A class for calling Inkscape to perform operations on a document"""
    def __init__(self, svg_document=None):
        self.command=""
        self.has_selection=False
        self.has_action=False
        self.svg_document=svg_document

    def set_svg_document(self, svg_document):
        self.svg_document=svg_document

    def clear(self):
        """Clear the action"""
        self.command=""
        self.has_action=False
        self.has_selection=False

    def verb(self,verb):
        if self.has_selection:
            self.command+="--verb=%s " % (verb)

            if not self.has_action:
                self.has_action=True

    def select_id(self,object_id):
        self.command+="--select='%s' " % (object_id)
        if not self.has_selection:
            self.has_selection=True

    def select_node(self,node):
        id = node.get("id",None)
        if id is None:
            raise Exception("Node has no id")
        self.select_id(id)

    def select_nodes(self,nodes):
        for node in nodes:
            self.select_node(node)

    def select_xpath(self,xpath, namespaces=NSS):
        nodes=self.svg_document.xpath(xpath, namespaces=namespaces)

        self.select_nodes(nodes)

    def deselect(self):
        if self.has_selection:
            self.verb("EditDeselect")
            self.has_selection=False

    def run_file(self,filename):
        """Run the actions on a specific file"""
        if not self.has_action:
            return

        cmd = "--verb=UnlockAllInAllLayers" + self.command + "--verb=FileSave --verb=FileQuit"
        if bsubprocess:
            p = Popen('inkscape "%s" %s' % (filename, cmd), shell=True, stdout=PIPE, stderr=PIPE)
            rc = p.wait()
            f = p.stdout
            err = p.stderr
        else:
            _,f,err = os.popen3( "inkscape %s %s" % ( filename, cmd ) )

        f.close()
        err.close()

    def run_document(self):
        """Run the actions on an svg xml tree"""
        if not self.has_action:
            return self.svg_document

        # First save the document
        svgfile = tempfile.mktemp(".svg")
        self.svg_document.write(svgfile)

        # Run the action on the document
        self.run_file(svgfile)

        # Open the resulting file
        stream = open(svgfile,'r')
        new_svg_doc = etree.parse(stream)
        stream.close()

        # Clean up.
        try:
            os.remove(svgfile)
        except Exception:
            pass

        # Set the current SVG document
        self.svg_document=new_svg_doc

        # Return the new document
        return new_svg_doc    

class SynfigExportActionGroup(InkscapeActionGroup):
    """An action group with stock commands designed for Synfig exporting"""
    def objects_to_paths(self):
        non_paths = [
            "svg:flowRoot", # Flowed text
            "svg:text",     # Text
            "svg:polygon", # Polygons
            "svg:circle", #Circle
            "svg:ellipse", #Ellipse
            "svg:rect" #Rectangles
            ]

        # Build an xpath command to select these nodes
        xpath_cmd=" | ".join(["//" + np for np in non_paths])

        # Note: already selected elements are not deselected

        # Select all of these elements
        self.select_xpath(xpath_cmd, namespaces=NSS)

        # Convert them to paths
        self.verb("ObjectToPath")
        self.deselect()

    def unlink_clones(self):
        self.select_xpath("//svg:use", namespaces=NSS)
        self.verb("EditUnlinkClone")
        self.deselect()

###### Utility Functions ##################################

def debug(obj):
    sys.stderr.write(str(obj))

### Path related

def fuse_subpaths(path_node):
    """Fuses subpaths of a path. Should only be used on unstroked paths"""
    simpletransform.fuseTransform(path_node)
    path_d=path_node.get("d",None)
    path=simplepath.parsePath(path_d)

    i = 0
    return_stack=[]
    while i<len(path):
        # Skip all elements that do not begin a new path
        if path[i][0] != "Z":
            if i>0 and path[i][0]=="M":
                path[i][0]='L'
            else:
                i+=1
                continue


        # We hit a terminator, or this element begins a new path
        prev_coords=[]
            
        if i+1 < len(path):
            # If this is not the last element of the path

            # Store the coordinates of the previous element
            prev_coords=[ path[i-1][1][-2], path[i-1][1][-1] ]

        # Remove the terminator, if there is one
        if path[i][0] == "Z":
            path.remove(["Z",[]])
            i-=1

        # Pop the top element of the return stack
        if return_stack!=[]:
            el = ['L', return_stack.pop()]
            i+=1
            path.insert(i,el)

        if prev_coords!=[]:
            return_stack.append(prev_coords)
            prev_coords=[]

        if i+1 < len(path):
            # If the next element is a moveto swap it for a line-to

            if path[i+1][0]=='M':
                path[i+1][0]='L'

        else:
            # If this is the last element of the path
            path.append(["Z",[]])
            break

        i+=1
    #end while

    path_d=simplepath.formatPath(path)
    path_node.set("d",path_d)
        
def split_fill_and_stroke(path_node):
    style=simplestyle.parseStyle(path_node.get("style",""))
    # If there is only stroke or only fill, don't split anything
    if "fill" in style.keys() and style["fill"] == "none":
        if "stroke" not in style.keys() or style["stroke"] == "none":
            return [None, None] # Path has neither stroke nor fill
        else:
            return [None, path_node]
    if "stroke" not in style.keys() or style["stroke"] == "none":
        return [path_node, None]

    group=path_node.makeelement(addNS("g","svg"))
    fill = etree.SubElement(group,addNS("path","svg"))
    stroke = etree.SubElement(group,addNS("path","svg"))

    attribs = path_node.attrib

    if "d" in attribs.keys():
        d=attribs["d"]
        del attribs["d"]
    else:
        raise AssertionError, "Cannot split stroke and fill of non-path element"

    if addNS("nodetypes", "sodipodi") in attribs.keys():
        nodetypes = attribs[addNS("nodetypes", "sodipodi")]
        del attribs[addNS("nodetypes", "sodipodi")]
    else:
        nodetypes = None

    if "id" in attribs.keys():
        path_id=attribs["id"]
        del attribs["id"]
    else:
        path_id=str(id(path_node))

    if "style" in attribs.keys():
        del attribs["style"]

    if "transform" in attribs.keys():
        transform=attribs["transform"]
        del attribs["transform"]
    else:
        transform=None

    # Pass along all remaining attributes to the group
    for attrib_name in attribs.keys():
        group.set(attrib_name,attribs[attrib_name])

    group.set("id",path_id)
        
    # Next split apart the style attribute
    style_group={}
    style_fill={"stroke":"none"}
    style_stroke={"fill":"#000000"}

    for key in style.keys():
        if key.startswith("fill"):
            style_fill[key]=style[key]
        elif key.startswith("stroke"):
            style_stroke[key]=style[key]
        elif key.startswith("marker"):
            style_stroke[key]=style[key]
        elif key.startswith("filter"):
            style_group[key]=style[key]
        else:
            style_fill[key]=style[key]
            style_stroke[key]=style[key]

    if len(style_group) != 0:
        group.set("style",simplestyle.formatStyle(style_group))

    fill.set("style",simplestyle.formatStyle(style_fill))
    stroke.set("style",simplestyle.formatStyle(style_stroke))

    # Finalize the two paths
    fill.set("d",d)
    stroke.set("d",d) 
    if nodetypes is not None:
        fill.set(addNS("nodetypes","sodipodi"),nodetypes)
        stroke.set(addNS("nodetypes","sodipodi"),nodetypes)
    fill.set("id",path_id+"-fill")
    stroke.set("id",path_id+"-stroke") 
    if transform is not None:
        fill.set("transform",transform)
        stroke.set("transform",transform)


    # Replace the original node with the group
    path_node.getparent().replace(path_node,group)

    return [fill, stroke]

### Object related

def propagate_attribs(node,parent_style={},parent_transform=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):
    """Propagate style and transform to remove inheritance"""
    if node.tag == addNS("svg","svg"):
        # TODO: parse "svg" elements with style or transform attribs
        for c in node.iterchildren():
            if c.tag == addNS("namedview", "sodipodi"):
                continue
            elif c.tag == addNS("defs", "svg"):
                continue
            elif c.tag == addNS("metadata", "svg"):
                continue
            else:
                propagate_attribs(c,parent_style,parent_transform)

    # Now only graphical elements remain


    # Compose the transform matrices
    this_transform=simpletransform.parseTransform(node.get("transform"))
    this_transform=simpletransform.composeTransform(parent_transform,this_transform)

    # Compose the style attribs
    this_style=simplestyle.parseStyle(node.get("style",""))
    remaining_style={} # Style attributes that are not propagated

    non_propagated=["filter"] # Filters should remain on the topmost ancestor
    for key in non_propagated:
        if key in this_style.keys():
            remaining_style[key]=this_style[key]
            del this_style[key]

    # Create a copy of the parent style, and merge this style into it
    parent_style_copy = parent_style.copy()
    parent_style_copy.update(this_style)
    this_style = parent_style_copy

    if node.tag == addNS("g","svg") or node.tag == addNS("a","svg"):
        # Leave only non-propagating style attributes
        if len(remaining_style) == 0:
            if "style" in node.keys():
                del node.attrib["style"]
        else:
            node.set("style",simplestyle.formatStyle(remaining_style))

        # Remove the transform attribute
        if "transform" in node.keys():
            del node.attrib["transform"]

        # Continue propagating on subelements
        for c in node.iterchildren():
            propagate_attribs(c,this_style,this_transform)
    else:
        # This element is not a container

        # Merge remaining_style into this_style
        this_style.update(remaining_style)

        # Set the element's style and transform attribs
        node.set("style",simplestyle.formatStyle(this_style))
        node.set("transform",simpletransform.formatTransform(this_transform))

###### Main Class #########################################
class SynfigPrep(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)

    def effect(self):
        """Transform document in preparation for exporting it into the Synfig format"""

        a = SynfigExportActionGroup(self.document)
        a.objects_to_paths()
        a.unlink_clones()
        self.document=a.run_document()

        # Remove inheritance of attributes
        propagate_attribs(self.document.getroot())

        # Fuse multiple subpaths in fills
        for node in self.document.xpath('//svg:path', namespaces=NSS):
            if node.get("d","").lower().count("m") > 1:
                # There are multiple subpaths
                fill = split_fill_and_stroke(node)[0]
                if fill is not None:
                    fuse_subpaths(fill)

if __name__ == '__main__':
    e = SynfigPrep()
    e.affect()


# vim: expandtab shiftwidth=4 tabstop=8 softtabstop=4 encoding=utf-8 textwidth=99
