# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from ast import literal_eval

import bpy
from bpy.props import BoolProperty, StringProperty, FloatProperty

import sverchok
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import (
    handle_read,
    handle_write,
    handle_delete,
    SvSetSocketAnyType,
    updateNode)


class svModalObjUpdater(bpy.types.Operator, object):

    """Operator which runs its self from a timer"""
    bl_idname = "wm.sv_obj_modal_update"
    bl_label = "start n stop obj updating"

    _timer = None
    mode = StringProperty(default='')
    node_name = StringProperty(default='')
    node_group = StringProperty(default='')
    speed = FloatProperty(default=0.2)

    def modal(self, context, event):
        if self.node_group and self.node_name:
            ng = bpy.data.node_groups.get(self.node_group)
            n = ng.nodes[self.node_name]
        else:
            return {'PASS_THROUGH'}

        if not (event.type == 'TIMER'):
            return {'PASS_THROUGH'}

        if not n.active:
            self.cancel(context)
            return {'FINISHED'}

        ''' reaches here only if event is TIMER and n.active '''
        print('calling process on:', n.name)
        n.process()
        return {'PASS_THROUGH'}

    def event_dispatcher(self, context, type_op):
        if type_op == 'start':
            context.node.active = True
            wm = context.window_manager
            self._timer = wm.event_timer_add(self.speed, context.window)
            wm.modal_handler_add(self)

        if type_op == 'end':
            context.node.active = False

    def execute(self, context):
        n = context.node
        self.node_name = context.node.name
        self.node_group = context.node.id_data.name

        self.event_dispatcher(context, self.mode)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


class SvObjSelected(bpy.types.Operator):
    """ G E T   SELECTED OBJECTS """
    bl_idname = "node.sverchok_object_insertion"
    bl_label = "Sverchok object selector"
    bl_options = {'REGISTER', 'UNDO'}

    node_name = StringProperty(
        name='name node', description='it is name of node',
        default='')

    tree_name = StringProperty(
        name='name tree', description='it is name of tree',
        default='')

    grup_name = StringProperty(
        name='grup tree', description='it is name of group',
        default='')

    sort = BoolProperty(
        name='sort objects', description='to sort objects by name or not',
        default=True)

    def enable(self, name_no, name_tr, handle, sorting):

        objects = []
        if self.grup_name and bpy.data.groups[self.grup_name].objects:
            objs = bpy.data.groups[self.grup_name].objects
        elif bpy.context.selected_objects:
            objs = bpy.context.selected_objects
        else:
            self.report({'WARNING'}, 'No object selected')
            return

        for o in objs:
            objects.append(o.name)
        if sorting:
            objects.sort()

        handle_write(name_no + name_tr, objects)

        if bpy.data.node_groups[name_tr]:
            handle = handle_read(name_no + name_tr)
            bpy.data.node_groups[name_tr].nodes[name_no].objects_local = str(handle[1])

    def disable(self, name, handle):
        if not handle[0]:
            return
        handle_delete(name)

    def execute(self, context):
        name_no = self.node_name
        name_tr = self.tree_name
        sorting = self.sort
        handle = handle_read(name_no+name_tr)
        self.disable(name_no+name_tr, handle)
        self.enable(name_no, name_tr, handle, sorting)
        print('have got {0} items from scene.'.format(handle[1]))
        return {'FINISHED'}


class ObjectsNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Objects Input slot '''
    bl_idname = 'ObjectsNode'
    bl_label = 'Objects_in'
    bl_icon = 'OUTLINER_OB_EMPTY'

    def hide_show_versgroups(self, context):
        if self.vergroups and not ('Vers_grouped' in self.outputs):
            self.outputs.new('StringsSocket', "Vers_grouped", "Vers_grouped")
        elif not self.vergroups and ('Vers_grouped' in self.outputs):
            self.outputs.remove(self.outputs['Vers_grouped'])

    objects_local = StringProperty(
        name='local objects in', description='objects, binded to current node',
        default='', update=updateNode)

    groupname = StringProperty(
        name='groupname', description='group of objects (green outline CTRL+G)',
        default='',
        update=updateNode)

    modifiers = BoolProperty(
        name='Modifiers',
        description='Apply modifier geometry to import (original untouched)',
        default=False,
        update=updateNode)

    vergroups = BoolProperty(
        name='Vergroups',
        description='Use vertex groups to nesty insertion',
        default=False,
        update=hide_show_versgroups)

    sort = BoolProperty(
        name='sort by name',
        description='sorting inserted objects by names',
        default=True,
        update=updateNode)

    active = BoolProperty(
        name='live update',
        default=0,
        update=updateNode
        )

    def sv_init(self, context):
        self.outputs.new('VerticesSocket', "Vertices", "Vertices")
        self.outputs.new('StringsSocket', "Edges", "Edges")
        self.outputs.new('StringsSocket', "Polygons", "Polygons")
        self.outputs.new('MatrixSocket', "Matrixes", "Matrixes")

    def draw_buttons(self, context, layout):
        row = layout.row()
        addon = context.user_preferences.addons.get(sverchok.__name__)
        if addon.preferences.over_sized_buttons:
            row.scale_y = 4.0
            op_text = "G E T"
        else:
            row.scale_y = 1
            op_text = "Get selection"

        opera = row.operator('node.sverchok_object_insertion', text=op_text)
        opera.node_name = self.name
        opera.tree_name = self.id_data.name
        opera.grup_name = self.groupname
        opera.sort = self.sort
        row = layout.row(align=True)
        row.prop(self, 'groupname', text='')
        row.prop(self, 'sort', text='Sort objects')

        row = layout.row(align=True)
        row.prop(self, "modifiers", text="Post modifiers")
        # row = layout.row(align=True)
        row.prop(self, "vergroups", text="Vert groups")

        handle = handle_read(self.name+self.id_data.name)
        if self.objects_local:
            if handle[0]:
                for i, o in enumerate(handle[1]):
                    if i > 4:
                        layout.label('. . . more '+str(len(handle[1])-5)+' items')
                        break
                    layout.label(o)
            else:
                handle_write(self.name+self.id_data.name, literal_eval(self.objects_local))
        else:
            layout.label('--None--')

        # Live Update Modal trigger. Verbose for now.
        row = layout.row()
        if self.active:
            row.operator('wm.sv_obj_modal_update', text='Press to stop live update').mode = 'end'
        else:
            row.operator('wm.sv_obj_modal_update', text='Press to start live update').mode = 'start'

    def update(self):
        pass

    def process(self):
        name = self.name + self.id_data.name
        handle = handle_read(name)
        #reload handle if possible
        if self.objects_local and not handle[0]:
            handle_write(name, literal_eval(self.objects_local))
            handle = handle_read(name)

        if handle[0]:
            objs = handle[1]
            edgs_out = []
            vers_out = []
            vers_out_grouped = []
            pols_out = []
            mtrx_out = []
            for obj_ in objs:  # names of objects
                edgs = []
                vers = []
                vers_grouped = []
                pols = []
                mtrx = []
                obj = bpy.data.objects[obj_]  # objects itself
                if obj.type == 'EMPTY':
                    for m in obj.matrix_world:
                        mtrx.append(m[:])

                else:
                    scene = bpy.context.scene
                    settings = 'PREVIEW'
                    # create a temporary mesh
                    obj_data = obj.to_mesh(scene, self.modifiers, settings)

                    for m in obj.matrix_world:
                        mtrx.append(list(m))
                    for k, v in enumerate(obj_data.vertices):
                        if self.vergroups and v.groups.values():
                            vers_grouped.append(k)
                        vers.append(list(v.co))
                    edgs = obj_data.edge_keys
                    for p in obj_data.polygons:
                        pols.append(list(p.vertices))
                    # remove the temp mesh
                    bpy.data.meshes.remove(obj_data)

                edgs_out.append(edgs)
                vers_out.append(vers)
                vers_out_grouped.append(vers_grouped)
                pols_out.append(pols)
                mtrx_out.append(mtrx)
            if vers_out[0]:

                if self.outputs['Vertices'].is_linked:
                    SvSetSocketAnyType(self, 'Vertices', vers_out)

                if self.outputs['Edges'].is_linked:
                    SvSetSocketAnyType(self, 'Edges', edgs_out)

                if self.outputs['Polygons'].is_linked:
                    SvSetSocketAnyType(self, 'Polygons', pols_out)

                if self.vergroups and self.outputs['Vers_grouped'].is_linked:
                    SvSetSocketAnyType(self, 'Vers_grouped', vers_out_grouped)

            if self.outputs['Matrixes'].is_linked:
                SvSetSocketAnyType(self, 'Matrixes', mtrx_out)


def register():
    bpy.utils.register_class(SvObjSelected)
    bpy.utils.register_class(ObjectsNode)
    bpy.utils.register_class(svModalObjUpdater)


def unregister():
    bpy.utils.unregister_class(svModalObjUpdater)
    bpy.utils.unregister_class(ObjectsNode)
    bpy.utils.unregister_class(SvObjSelected)


if __name__ == '__main__':
    register()
