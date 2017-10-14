#    Copyright (C) 2014 Jeremy S. Sanders
#    Email: Jeremy Sanders <jeremy@jeremysanders.net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
##############################################################################

"""Widget to plot axes, and to handle conversion of coordinates to plot
positions."""

from __future__ import division
import math
import numpy as N
import itertools

from . import widget
from . import axisticks
from .axis import AxisLabel, TickLabel, AutoRange
from ..compat import czip
from .. import qtall as qt4
from .. import document
from .. import setting
from .. import utils

try:
    from ..helpers import threed
except ImportError:
    # compatibility if threed is not compiled
    class _dummy:
        def __init__(self):
            self.AxisTickLabels = object
    threed = _dummy()

def _(text, disambiguation=None, context='Axis3D'):
    """Translate text."""
    return qt4.QCoreApplication.translate(context, text, disambiguation)

class _AxisTickLabels(threed.AxisTickLabels):
    """For drawing tick labels."""

    def __init__(self, box1, box2, fracs, labels, labelsprop):
        threed.AxisTickLabels.__init__(self, box1, box2, fracs)
        self.labels = labels
        self.labelsprop = labelsprop

    def drawLabel(self, painter, index, pt, ax1, ax2, quad, dirn):
        """Draw the label, as requested by the Scene."""

        font = self.labelsprop.makeQFont(painter)
        painter.setFont(font)
        pen = self.labelsprop.makeQPen(painter)
        painter.setPen(pen)

        label = self.labels[index]
        renderer = utils.Renderer(
            painter, font, 0, 0, label, alignhorz=0, alignvert=0)
        bounds = renderer.getBounds()
        width, height = bounds[2]-bounds[0], bounds[3]-bounds[1]

        fm = qt4.QFontMetricsF(font, painter.device())
        height += fm.ascent()
        width += fm.ascent()*0.5

        # is the axis more horizontal than vertical?
        dx, dy = ax2.x()-ax1.x(), ax2.y()-ax1.y()
        horz = abs(dx) > abs(dy)

        if horz:
            # t=tan theta
            t = abs(dy/dx)
            # these are shifts reqired so that text bounding box does
            # not hit axis
            hshift = t*(height*0.5+t*width *0.5)/(1+t*t)
            vshift = t*(width *0.5-t*height*0.5)/(1+t*t)

            if quad == 0 or quad == 2:
                # top horizontal axis: text at top
                yoffset = -height*0.5-vshift
                xoffset = hshift if dy/dx>=0 else -hshift
            else:
                # bottom horizontal axis: text at top
                yoffset = height*0.5+vshift
                xoffset = -hshift if dy/dx>=0 else hshift

        else:
            t = abs(dx/dy)
            vshift = t*(width *0.5+t*height*0.5)/(1+t*t)
            hshift = t*(height*0.5-t*width *0.5)/(1+t*t)

            if quad == 2 or quad == 3:
                # left vertical axis: text at left
                xoffset = -width*0.5-hshift
                yoffset = vshift if dx/dy >= 0 else -vshift
            else:
                # right vertical axis: text at right
                xoffset = width*0.5+hshift
                yoffset = -vshift if dx/dy >= 0 else vshift

        # painter.setPen(qt4.QPen(qt4.QColor("red")))
        # painter.drawEllipse(qt4.QRectF(
        #     pt.x()-2, pt.y()-2, 4, 4))

        # painter.setPen(qt4.QPen())
        # painter.drawRect(qt4.QRectF(
        #     qt4.QPointF(pt.x()+xoffset-width*0.5, pt.y()+yoffset-height*0.5),
        #     qt4.QPointF(pt.x()+xoffset+width*0.5, pt.y()+yoffset+height*0.5)
        # ))

        painter.translate(pt.x()+xoffset, pt.y()+yoffset)
        renderer.render()

# class _AxisTickText(threed.Text):
#     """For drawing text at 3D locations."""
#     def __init__(self, posns, posnsalong, textlist, labelprop, params):
#         threed.Text.__init__(
#             self, threed.ValVector(posns), threed.ValVector(posnsalong))
#         self.textlist = textlist
#         self.labelprop = labelprop
#         self.params = params

#     def draw(self, painter, pt1, pt2, index, scale, linescale):
#         painter.save()
#         painter.setPen(qt4.QPen())

#         font = self.labelprop.makeQFont(painter)
#         fm = utils.FontMetrics(font, painter.device())
#         offset = self.labelprop.get('offset').convert(painter)
#         offset += fm.leading() + fm.descent()

#         # convert offset into perp dirn from delpt
#         # normalise vector

#         delpt = (pt2.x()-pt1.x(), pt2.y()-pt1.y())
#         scale = offset / math.sqrt(delpt[0]**2+delpt[1]**2)
#         delpt = (delpt[0]*scale, delpt[1]*scale)

#         ptrans = qt4.QPointF(pt1.x()-delpt[1], pt1.y()+delpt[0])

#         painter.translate(ptrans)

#         angle = math.atan2(delpt[1], delpt[0]) * 180/math.pi
#         # prevent text going upside down
#         alignvert = 1
#         #if angle < -90 or angle > 90:
#         #    angle = 180+angle
#         #    #alignvert = -alignvert
#         painter.rotate(angle)
#         r = utils.Renderer(
#             painter, font, 0, 0, self.textlist[index],
#             alignhorz=0, alignvert=alignvert)
#         r.render()
#         painter.restore()

class MajorTick(setting.Line3D):
    '''Major tick settings.'''

    def __init__(self, name, **args):
        setting.Line3D.__init__(self, name, **args)
        self.get('color').newDefault('grey')
        self.add(setting.Float(
            'length',
            20.,
            descr = _('Length of major ticks'),
            usertext= _('Length')))
        self.add(setting.Int(
            'number',
            6,
            descr = _('Number of major ticks to aim for'),
            usertext= _('Number')))
        self.add(setting.FloatList(
            'manualTicks',
            [],
            descr = _('List of tick values'
                      ' overriding defaults'),
            usertext= _('Manual ticks')))

class MinorTick(setting.Line3D):
    '''Minor tick settings.'''

    def __init__(self, name, **args):
        setting.Line3D.__init__(self, name, **args)
        self.get('color').newDefault('grey')
        self.add( setting.Float(
            'length',
            10,
            descr = _('Length of minor ticks'),
            usertext= _('Length')))
        self.add( setting.Int(
            'number',
            20,
            descr = _('Number of minor ticks to aim for'),
            usertext= _('Number')))

class GridLine(setting.Line3D):
    '''Grid line settings.'''

    def __init__(self, name, **args):
        setting.Line3D.__init__(self, name, **args)

        self.get('color').newDefault('grey')
        self.get('hide').newDefault(True)

class MinorGridLine(setting.Line3D):
    '''Minor tick grid line settings.'''

    def __init__(self, name, **args):
        setting.Line3D.__init__(self, name, **args)

        self.get('color').newDefault('lightgrey')
        self.get('hide').newDefault(True)

class Axis3D(widget.Widget):
    """Manages and draws an axis."""

    typename = 'axis3d'
    allowusercreation = True
    description = _('3D axis')
    isaxis = True
    isaxis3d = True

    def __init__(self, parent, name=None):
        """Initialise axis."""

        widget.Widget.__init__(self, parent, name=name)
        s = self.settings

        for n in ('x', 'y', 'z'):
            if self.name == n and s.direction != n:
                s.direction = n

        # automatic range
        self.setAutoRange(None)

        # document updates change set variable when things need recalculating
        self.docchangeset = -1

    @classmethod
    def addSettings(klass, s):
        """Construct list of settings."""
        widget.Widget.addSettings(s)
        s.add( setting.Str(
            'label', '',
            descr=_('Axis label text'),
            usertext=_('Label')) )
        s.add( setting.AxisBound(
            'min', 'Auto',
            descr=_('Minimum value of axis'),
            usertext=_('Min')) )
        s.add( setting.AxisBound(
            'max', 'Auto',
            descr=_('Maximum value of axis'),
            usertext=_('Max')) )
        s.add( setting.Bool(
            'log', False,
            descr = _('Whether axis is logarithmic'),
            usertext=_('Log')) )
        s.add( AutoRange(
            'autoRange', 'next-tick') )
        s.add( setting.Choice(
            'mode',
            ('numeric', 'datetime', 'labels'),
            'numeric',
            descr = _('Type of ticks to show on on axis'),
            usertext=_('Mode')) )

        s.add( setting.Bool(
            'autoMirror', True,
            descr = _('Place axis on opposite side of graph '
                      'if none'),
            usertext=_('Auto mirror'),
            formatting=True) )
        s.add( setting.Bool(
            'reflect', False,
            descr = _('Place axis text and ticks on other side'
                      ' of axis'),
            usertext=_('Reflect'),
            formatting=True) )
        s.add( setting.Bool(
            'outerticks', False,
            descr = _('Place ticks on outside of graph'),
            usertext=_('Outer ticks'),
            formatting=True) )

        s.add( setting.Float(
            'datascale', 1.,
            descr=_('Scale data plotted by this factor'),
            usertext=_('Scale')) )

        s.add( setting.Choice(
            'direction',
            ['x', 'y', 'z'],
            'x',
            descr = _('Direction of axis'),
            usertext=_('Direction')) )
        s.add( setting.Float(
            'lowerPosition', 0.,
            descr=_('Fractional position of lower end of '
                    'axis on graph'),
            usertext=_('Min position')) )
        s.add( setting.Float(
            'upperPosition', 1.,
            descr=_('Fractional position of upper end of '
                    'axis on graph'),
            usertext=_('Max position')) )
        s.add( setting.Float(
            'otherPosition1', 0.,
            descr=_('Fractional position of axis '
                    'in its perpendicular direction 1'),
            usertext=_('Axis position 1')) )
        s.add( setting.Float(
            'otherPosition2', 0.,
            descr=_('Fractional position of axis '
                    'in its perpendicular direction 2'),
            usertext=_('Axis position 2')) )

        s.add( setting.Line3D(
            'Line',
            descr = _('Axis line settings'),
            usertext = _('Axis line')),
               pixmap='settings_axisline' )
        s.add( AxisLabel(
            'Label',
            descr = _('Axis label settings'),
            usertext = _('Axis label')),
               pixmap='settings_axislabel' )
        s.add( TickLabel(
            'TickLabels',
            descr = _('Tick label settings'),
            usertext = _('Tick labels')),
               pixmap='settings_axisticklabels' )
        s.add( MajorTick(
            'MajorTicks',
            descr = _('Major tick line settings'),
            usertext = _('Major ticks')),
               pixmap='settings_axismajorticks' )
        s.add( MinorTick(
            'MinorTicks',
            descr = _('Minor tick line settings'),
            usertext = _('Minor ticks')),
               pixmap='settings_axisminorticks' )
        s.add( GridLine(
            'GridLines',
            descr = _('Grid line settings'),
            usertext = _('Grid lines')),
               pixmap='settings_axisgridlines' )
        s.add( MinorGridLine(
            'MinorGridLines',
            descr = _('Minor grid line settings'),
            usertext = _('Grid lines for minor ticks')),
               pixmap='settings_axisminorgridlines' )

    @classmethod
    def allowedParentTypes(self):
        from . import graph3d
        return (graph3d.Graph3D,)

    @property
    def userdescription(self):
        """User friendly description."""
        s = self.settings
        return "range %s to %s%s" % ( str(s.min), str(s.max),
                                      ['',' (log)'][s.log])

    def isLinked(self):
        """Whether is an axis linked to another."""
        return False

    def setAutoRange(self, autorange):
        """Set the automatic range of this axis (called from page helper)."""

        if autorange:
            scale = self.settings.datascale
            self.autorange = ar = [x*scale for x in autorange]
            if self.settings.log:
                ar[0] = max(1e-99, ar[0])
        else:
            if self.settings.log:
                self.autorange = [1e-2, 1.]
            else:
                self.autorange = [0., 1.]

    def usesAutoRange(self):
        """Return whether any of the bounds are automatically determined."""
        return self.settings.min == 'Auto' or self.settings.max == 'Auto'

    def computePlottedRange(self, force=False, overriderange=None):
        """Convert the range requested into a plotted range."""

        if self.docchangeset == self.document.changeset and not force:
            return

        s = self.settings
        if overriderange is None:
            self.plottedrange = [s.min, s.max]
        else:
            self.plottedrange = overriderange

        # automatic lookup of minimum
        if overriderange is None:
            if s.min == 'Auto':
                self.plottedrange[0] = self.autorange[0]
            if s.max == 'Auto':
                self.plottedrange[1] = self.autorange[1]

        # yuck, but sometimes it's true
        # tweak range to make sure things don't blow up further down the
        # line
        if ( abs(self.plottedrange[0] - self.plottedrange[1]) <
             ( abs(self.plottedrange[0]) + abs(self.plottedrange[1]) )*1e-8 ):
               self.plottedrange[1] = ( self.plottedrange[0] +
                                        max(1., self.plottedrange[0]*0.1) )

        # handle axis values round the wrong way
        invertaxis = self.plottedrange[0] > self.plottedrange[1]
        if invertaxis:
            self.plottedrange = self.plottedrange[::-1]

        # make sure log axes don't blow up
        if s.log:
            if self.plottedrange[0] < 1e-99:
                self.plottedrange[0] = 1e-99
            if self.plottedrange[1] < 1e-99:
                self.plottedrange[1] = 1e-99
            if self.plottedrange[0] == self.plottedrange[1]:
                self.plottedrange[1] = self.plottedrange[0]*2

        s.get('autoRange').adjustPlottedRange(
            self.plottedrange, s.min=='Auto', s.max=='Auto', s.log, self.document)

        self.computeTicks()

        # invert bounds if axis was inverted
        if invertaxis:
            self.plottedrange = self.plottedrange[::-1]

        self.docchangeset = self.document.changeset

    def computeTicks(self, allowauto=True):
        """Update ticks given plotted range.
        if allowauto is False, then do not allow ticks to be
        updated
        """

        s = self.settings

        if s.mode in ('numeric', 'labels'):
            tickclass = axisticks.AxisTicks
        else:
            tickclass = axisticks.DateTicks

        nexttick = s.autoRange == 'next-tick'
        extendmin = nexttick and s.min == 'Auto' and allowauto
        extendmax = nexttick and s.max == 'Auto' and allowauto

        # create object to compute ticks
        axs = tickclass(self.plottedrange[0], self.plottedrange[1],
                        s.MajorTicks.number, s.MinorTicks.number,
                        extendmin = extendmin, extendmax = extendmax,
                        logaxis = s.log )

        axs.getTicks()
        self.plottedrange[0] = axs.minval
        self.plottedrange[1] = axs.maxval
        self.majortickscalc = axs.tickvals
        self.minortickscalc = axs.minorticks
        self.autoformat = axs.autoformat

        # override values if requested
        if len(s.MajorTicks.manualTicks) > 0:
            ticks = []
            for i in s.MajorTicks.manualTicks:
                if i >= self.plottedrange[0] and i <= self.plottedrange[1]:
                    ticks.append(i)
            self.majortickscalc = N.array(ticks)

    def getPlottedRange(self):
        """Return the range plotted by the axes."""
        self.computePlottedRange()
        return (self.plottedrange[0], self.plottedrange[1])

    def dataToLogicalCoords(self, vals):
        """Compute coordinates on graph to logical graph coordinates (0..1)"""

        self.computePlottedRange()
        s = self.settings

        svals = vals * s.datascale
        if s.log:
            fracposns = self.logConvertToPlotter(svals)
        else:
            fracposns = self.linearConvertToPlotter(svals)

        lower, upper = s.lowerPosition, s.upperPosition
        return lower + fracposns*(upper-lower)

    def linearConvertToPlotter(self, v):
        """Convert graph coordinates to 0..1 coordinates"""
        return ( (v - self.plottedrange[0]) /
                 (self.plottedrange[1] - self.plottedrange[0]) )

    def logConvertToPlotter(self, v):
        """Convert graph coordinates to 0..1 coordinates"""
        log1 = N.log(self.plottedrange[0])
        log2 = N.log(self.plottedrange[1])
        return (N.log(N.clip(v, 1e-99, 1e99)) - log1) / (log2 - log1)

    def getAutoMirrorCombs(self):
        """Get combinations of other position for auto mirroring."""
        s = self.settings
        op1 = s.otherPosition1
        op2 = s.otherPosition2
        if not s.autoMirror:
            return ((op1, op2),)
        if op1 == 0 or op1 == 1:
            op1list = [1, 0]
        else:
            op1list = [op1]
        if op2 == 0 or op2 == 1:
            op2list = [1, 0]
        else:
            op2list = [op2]
        return itertools.product(op1list, op2list)

    def addAxisLine(self, painter, cont, dirn):
        """Build list of lines to draw axis line, mirroring if necessary.

        Returns list of start and end points of axis lines
        """

        s = self.settings
        lower, upper = s.lowerPosition, s.upperPosition

        outstart = []
        outend = []
        for op1, op2 in self.getAutoMirrorCombs():
            if dirn == 'x':
                outstart += [(lower, op1, op2)]
                outend += [(upper, op1, op2)]
            elif dirn == 'y':
                outstart += [(op1, lower, op2)]
                outend += [(op1, upper, op2)]
            else:
                outstart += [(op1, op2, lower)]
                outend += [(op1, op2, upper)]

        if not s.Line.hide:
            startpts = threed.ValVector(N.ravel(outstart))
            endpts = threed.ValVector(N.ravel(outend))
            lineprop = s.Line.makeLineProp(painter)
            cont.addObject(threed.LineSegments(startpts, endpts, lineprop))

        return list(zip(outstart, outend))

    def addTickLabels(self, cont, linecoords, labelsprop, tickfracs,
                      tickvals):
        """Make tick labels for axis."""

        if labelsprop.hide:
            return

        # make strings for labels
        fmt = labelsprop.format
        if fmt.lower() == 'auto':
            fmt = self.autoformat
        scale = labelsprop.scale
        labels = [ utils.formatNumber(v*scale, fmt, locale=self.document.locale)
                   for v in tickvals ]

        atl = _AxisTickLabels(
            threed.Vec3(0,0,0), threed.Vec3(1,1,1),
            threed.ValVector(tickfracs),
            labels, labelsprop)
        for startpos, endpos in linecoords:
            atl.addAxisChoice(threed.Vec3(*startpos), threed.Vec3(*endpos))
        cont.addObject(atl)

    def addAxisTicks(self, painter, cont, dirn, linecoords, tickprops, labelsprop,
                     tickvals):
        """Add ticks for the vals and tick properties class given.
        linecoords: coordinates of start and end points of lines
        labelprops: properties of label, or None
        cont: container to add ticks
        dirn: 'x', 'y', 'z' for axis
        """

        ticklen = tickprops.length * 1e-3
        tfracs = self.dataToLogicalCoords(tickvals)

        outstart = []
        outend = []
        for op1, op2 in self.getAutoMirrorCombs():
            # where to draw tick from
            op1pts = N.full_like(tfracs, op1)
            op2pts = N.full_like(tfracs, op2)
            # where to draw tick to
            op1pts2 = N.full_like(tfracs, op1+ticklen*(1 if op1 < 0.5 else -1))
            op2pts2 = N.full_like(tfracs, op2+ticklen*(1 if op2 < 0.5 else -1))

            # the small 1e-3 offset is to define where up is on the label
            if dirn == 'x':
                ptsonaxis = (tfracs, op1pts, op2pts)
                ptsoff1 = (tfracs, op1pts2, op2pts)
                ptsoff2 = (tfracs, op1pts, op2pts2)
                ptsalong = (tfracs+1e-3, op1pts, op2pts)
            elif dirn == 'y':
                ptsonaxis = (op1pts, tfracs, op2pts)
                ptsoff1 = (op1pts2, tfracs, op2pts)
                ptsoff2 = (op1pts, tfracs, op2pts2)
                ptsalong = (op1pts, tfracs+1e-3, op2pts)
            else:
                ptsonaxis = (op1pts, op2pts, tfracs)
                ptsoff1 = (op1pts2, op2pts, tfracs)
                ptsoff2 = (op1pts, op2pts2, tfracs)
                ptsalong = (op1pts, op2pts, tfracs+1e-3)

            outstart += [N.ravel(N.column_stack(ptsonaxis)),
                         N.ravel(N.column_stack(ptsonaxis))]
            outend += [N.ravel(N.column_stack(ptsoff1)),
                       N.ravel(N.column_stack(ptsoff2))]

        if labelsprop is not None:
            self.addTickLabels(cont, linecoords, labelsprop, tfracs, tickvals)

        if not tickprops.hide:
            startpts = threed.ValVector(N.concatenate(outstart))
            endpts = threed.ValVector(N.concatenate(outend))
            lineprop = tickprops.makeLineProp(painter)
            cont.addObject(threed.LineSegments(startpts, endpts, lineprop))

    def drawToObject(self, painter):

        s = self.settings
        dirn = s.direction

        cont = threed.ObjectContainer()

        linecoords = self.addAxisLine(painter, cont, dirn)
        self.addAxisTicks(
            painter, cont, dirn, linecoords, s.MajorTicks, s.TickLabels,
            self.majortickscalc)
        self.addAxisTicks(
            painter, cont, dirn, linecoords, s.MinorTicks, None,
            self.minortickscalc)

        return cont

# allow the factory to instantiate an axis
document.thefactory.register(Axis3D)
