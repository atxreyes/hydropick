#
# Copyright (c) 2014, Texas Water Development Board
# All rights reserved.
#
# This code is open-source. See LICENSE file for details.
#

from __future__ import absolute_import

from traits.api import  DelegatesTo
from traitsui.api import View, UItem, TextEditor
from pyface.tasks.api import TraitsDockPane


class MessagePane(TraitsDockPane):
    """ The dock pane holding the data view of the survey """

    id = 'hydropick.message'
    name = "Status Messages"

    #: stores all messages for this session
    msg_string = DelegatesTo('task')

    traits_view = View(UItem('msg_string',
                             editor=TextEditor(read_only=True),
                             style='custom')
                       )
