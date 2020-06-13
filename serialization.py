# This file is part of jack_mixer
#
# Copyright (C) 2006 Nedko Arnaudov <nedko@arnaudov.name>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA.

class SerializationBackend:
    '''Base class for serialization backends'''
    def get_root_serialization_object(self, name):
        '''Returns serialization object where properties of root object
           will be serialized to'''
        # this method should never be called for the base class
        raise NotImplementedError

    def get_child_serialization_object(self, name, backend_object):
        # this method should never be called for the base class
        raise NotImplementedError

class SerializationObjectBackend:
    '''Base class for serialization backend objects where real object
       properties will be serialized to or unserialized from.'''
    def add_property(self, name, value):
        '''Serialize particular property'''
        pass

    def get_childs(self):
        pass

    def get_properties(self):
        pass

    def serialization_name(self):
        return None

class SerializedObject:
    '''Base class for object supporting serialization'''
    def serialization_name(self):
        return None

    def serialize(self, object_backend):
        '''Serialize properties of called object into supplied serialization_object_backend'''
        pass

    def serialization_get_childs(self):
        '''Get child objects tha required and support serialization'''
        return []

    def unserialize_property(self, name, value):
        pass

    def unserialize_child(self, name):
        return None

class Serializator:
    def __init__(self):
        pass

    def serialize(self, root, backend):
        self.serialize_one(backend, root, backend.get_root_serialization_object(root.serialization_name()))

    def unserialize(self, root, backend):
        backend_object = backend.get_root_unserialization_object(root.serialization_name())
        if backend_object == None:
            return False

        return self.unserialize_one(backend, root, backend_object)

    def unserialize_one(self, backend, object, backend_object):
        #print "Unserializing " + repr(object)
        properties = backend_object.get_properties()
        for name, value in properties.items():
            #print "%s = %s" % (name, value)
            if not object.unserialize_property(name, value):
                return False

        backend_childs = backend_object.get_childs()
        for backend_child in backend_childs:
            name = backend_child.serialization_name()
            child = object.unserialize_child(name)
            if not child:
                return False
            if not self.unserialize_one(backend, child, backend_child):
                return False

        return True

    def serialize_one(self, backend, object, backend_object):
        object.serialize(backend_object)
        childs = object.serialization_get_childs()
        for child in childs:
            #print "serializing child " + repr(child)
            self.serialize_one(backend, child,
                               backend.get_child_serialization_object(
                                       child.serialization_name(), backend_object))
