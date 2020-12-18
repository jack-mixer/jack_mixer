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

import xml.dom
import xml.dom.minidom

from serialization import SerializationBackend


class XmlSerialization(SerializationBackend):
    def get_root_serialization_object(self, name):
        self.doc = xml.dom.getDOMImplementation().createDocument(xml.dom.EMPTY_NAMESPACE, name, None)
        return XmlSerializationObject(self.doc, self.doc.documentElement)

    def get_root_unserialization_object(self, name):
        if name != self.doc.documentElement.nodeName:
            return None
        return XmlSerializationObject(self.doc, self.doc.documentElement)

    def get_child_serialization_object(self, name, backend_object):
        child = self.doc.createElement(name)
        backend_object.element.appendChild(child)
        return XmlSerializationObject(self.doc, child)

    def save(self, file):
        file.write(self.doc.toprettyxml())

    def load(self, file):
        self.doc = xml.dom.minidom.parse(file)


class XmlSerializationObject:
    def __init__(self, doc, element):
        self.doc = doc
        self.element = element

    def add_property(self, name, value):
        self.add_property_as_attribute(name, value)

    def add_property_as_attribute(self, name, value):
        self.element.setAttribute(name, value)

    #def add_property_as_child_element(self, name, value):
    #    child = self.doc.createElement(name)
    #    value = self.doc.createTextNode(value)
    #    child.appendChild(value)
    #    self.element.appendChild(child)

    def get_childs(self):
        child_elements = self.element.childNodes
        childs = []
        for child in child_elements:
            if child.nodeType == child.ELEMENT_NODE:
                childs.append(XmlSerializationObject(self.doc, child))
        return childs

    def get_properties(self):
        properties = self.element.attributes
        dictionary = {}
        for i in range(properties.length):
            dictionary[properties.item(i).name] = properties.item(i).nodeValue
        return dictionary

    def serialization_name(self):
        return self.element.nodeName
