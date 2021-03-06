#
# Copyright (C) 2016-2019 by Nathan Lovato, Daniel Oakey, Razvan Radulescu, and contributors
#
# This file is part of Power Sequencer.
#
# Power Sequencer is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# Power Sequencer is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Power Sequencer. If
# not, see <https://www.gnu.org/licenses/>.
#
import bpy
from operator import attrgetter

from .utils.global_settings import SequenceTypes
from .utils.functions import find_sequences_after, get_mouse_frame_and_channel, sequencer_workaround_2_80_audio_bug
from .utils.doc import doc_name, doc_idname, doc_brief, doc_description


def find_sequences_before(context, strip):
    """
    Returns a list of sequences that are before the strip in the current context
    """
    return [s for s in context.sequences if s.frame_final_end <= strip.frame_final_start]


class POWER_SEQUENCER_OT_concatenate_strips(bpy.types.Operator):
    """
    *brief* Remove space between strips

    Concatenates selected strips in a channel, i.e. removes the gap between them. If a single
    strip is selected, either the next strip in the channel will be concatenated, or all
    strips in the channel will be concatenated depending on which shortcut is used.
    """

    doc = {
        "name": doc_name(__qualname__),
        "demo": "https://i.imgur.com/YyEL8YP.gif",
        "description": doc_description(__doc__),
        "shortcuts": [
            (
                {"type": "C", "value": "PRESS"},
                {"concatenate_all": False, "to_left": True},
                ("Concatenate and select the next strip in the channel"),
            ),
            (
                {"type": "C", "value": "PRESS", "shift": True},
                {"concatenate_all": True, "to_left": True},
                "Concatenate all strips in selected channels",
            ),
            (
                {"type": "C", "value": "PRESS", "alt": True},
                {"concatenate_all": False, "to_left": False},
                ("Concatenate and select the previous strip in the channel towards the right"),
            ),
            (
                {"type": "C", "value": "PRESS", "shift": True, "alt": True},
                {"concatenate_all": True, "to_left": False},
                "Shift Alt C; Concatenate all strips in channel towards the right",
            ),
        ],
        "keymap": "Sequencer",
    }
    bl_idname = doc_idname(__qualname__)
    bl_label = doc["name"]
    bl_description = doc_brief(doc["description"])
    bl_options = {"REGISTER", "UNDO"}

    concatenate_all: bpy.props.BoolProperty(
        name="Concatenate all strips in channel",
        description=("If only one strip selected, concatenate" " the entire channel"),
        default=False,
    )
    to_left: bpy.props.BoolProperty(
        name="To Left",
        description="Concatenate strips moving them back in time (default) or forward in time",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return context.sequences

    def invoke(self, context, event):
        if not context.selected_sequences:
            frame, channel = get_mouse_frame_and_channel(context, event)
            bpy.ops.power_sequencer.select_closest_to_mouse(frame=frame, channel=channel)
        return self.execute(context)

    def execute(self, context):
        selection = context.selected_sequences
        channels = {s.channel for s in selection}

        if len(selection) == len(channels):
            for s in selection:
                candidates = (
                    find_sequences_before(context, s)
                    if not self.to_left
                    else find_sequences_after(context, s)
                )
                to_concatenate = [
                    strip
                    for strip in candidates
                    if strip.channel == s.channel
                    and not strip.lock
                    and strip.type in SequenceTypes.CUTABLE
                ]
                self.concatenate(s, to_concatenate)

        else:
            for channel in channels:
                to_concatenate = [s for s in selection if s.channel == channel]
                strip_target = (
                    min(to_concatenate, key=lambda s: s.frame_final_start)
                    if self.to_left
                    else max(to_concatenate, key=lambda s: s.frame_final_start)
                )
                to_concatenate.remove(strip_target)
                self.concatenate(strip_target, to_concatenate, force_all=True)

        sequencer_workaround_2_80_audio_bug(context)
        return {"FINISHED"}

    def concatenate(self, strip_target, sequences, force_all=False):
        to_concatenate = sorted(sequences, key=attrgetter("frame_final_start"))
        to_concatenate = list(reversed(to_concatenate)) if not self.to_left else to_concatenate
        to_concatenate = (
            [to_concatenate[0]] if not (self.concatenate_all or force_all) else to_concatenate
        )

        attribute_target = "frame_final_end" if self.to_left else "frame_final_start"
        attribute_concat = "frame_final_start" if self.to_left else "frame_final_end"
        concatenate_start = getattr(strip_target, attribute_target)
        last_gap = 0
        for s in to_concatenate:
            if isinstance(s, bpy.types.EffectSequence):
                concatenate_start = (
                    s.frame_final_end - last_gap if self.to_left else s.frame_final_start - last_gap
                )
                continue
            concat_strip_frame = getattr(s, attribute_concat)
            gap = concat_strip_frame - concatenate_start
            s.frame_start -= gap
            concatenate_start = s.frame_final_end if self.to_left else s.frame_final_start
            last_gap = gap

        if not self.concatenate_all:
            strip_target.select = False
            to_concatenate[0].select = True
