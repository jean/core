#--
# Copyright (c) 2008, 2009 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
#--

"""This module implements the component model of the framework.

This model is inspired by the Seaside one. With the possibility to embed,
replace and call a component. It's described in `ComponentModel`
"""

import sys
import types
import stackless

from peak.rules import when

from nagare import presentation

class AnswerWithoutCall(BaseException):
    pass


def call_wrapper(action, *args, **kw):
    """A wrapper that create a tasklet.
    
    It's necessary to wrapper a callable that do directly or indirectly a
    ``comp.call(o)`` into such a ``call_wrapper``.
    
    .. note::
        The actions your registred on the ``<a>`` tags or on the submit buttons
        are already wrapped for you.

    In:
      - ``action`` -- a callable. It will be called, wrapped into a new tasklet,
        with the ``args`` and ``kw`` parameters.
      - ``args`` -- positional parameters of the callable
      - ``kw`` -- keywords parameters of the callable

    Return:
      *Never*
    """
    stackless.tasklet(action)(*args, **kw).run()


class Component(object):
    """This class transforms any Python object into a component
    
    A component has views, can the embedded, replaced, called and can answsered a value.
    """
    def __init__(self, o, model=0, url=None):
        """Initialisation
        
        In:
          - ``o`` -- the python object (or component) to transform into a component
          - ``model`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component  
        """
        if isinstance(o, Component):
            o = o()

        self.o = o

        self._channel = None
        self.model = model
        self.url = url
        self._on_answer = None

    def __call__(self):
        """Return the inner object
        """
        return self.o

    def render(self, renderer, model=0):
        """Rendering method of a component
        
        Forward the call to the generic method of the ``presentation`` service
        """
        return presentation.render(self, renderer, self, model)

    def init(self, url, http_method, request):
        """Initialisation from an url
        
        Forward the call to the generic method of the ``presentation`` service
        """
        return presentation.init(self, url, self, http_method, request)

    def becomes(self, o, model=0, url=None):
        """Replace a component by an object or an other component
        
        In:
          - ``o`` -- object to be replaced by
          - ``model`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component
            
        Return:
          - ``self`` 
        """
        if isinstance(o, Component):
            o = o()

        self.o = o
        self.model = model
        self.url = url or self.url

        return self
    
    def call(self, o, model=0, url=None):
        """Call an other object or component
        
        The current component is replaced and will be back when the object
        will do an ``answer()``
        
        In:
          - ``o`` -- the object to call
          - ``model`` -- the name of the view to use (``None`` for the default view)
          - ``url`` -- the url fragment to add before all the links generated by
            views of this component
            
        Return:
          - the answer of the called object        
        """
        sys.exc_clear()

        if isinstance(o, Component):
            o = o()

        # Keep my configuration
        previous_o = self.o
        previous_model = self.model
        previous_url = self.url
        previous_channel = self._channel
        previous_on_answer = self._on_answer

        # Set the new configuration
        self._on_answer = None

        # Replace me by the object and wait its answer
        self.becomes(o, model, url)
        self._channel = stackless.channel()        
        r = self._channel.receive()
        
        # Restore my configuration
        self._on_answer = previous_on_answer
        self._channel = previous_channel
        self.url = previous_url
        self.becomes(previous_o, previous_model)

        # Return the answer
        return r

    def answer(self, r=None):
        """Answer to a call
        
        In:
          - the value to answer
        """
        # If a function is listening to my answer, calls it
        if self._on_answer is not None:
            return self._on_answer(r)

        # Else, check if I was called by a component
        if self._channel is None:
            raise AnswerWithoutCall()

        # Returns my answer to the calling component
        self._channel.send(r)

    def on_answer(self, f):
        """
        Register a function to listen to my answer
        
        In:
          - ``f`` -- function to call with my answer
        """
        self._on_answer = f
        return self
    
    def __repr__(self):
        return '<%s at %x on object %r>' % (
                                            self.__class__.__name__.lower(),
                                            id(self),
                                            self.o
                                           )

@when(presentation.render, (Component, object, object, int))
@when(presentation.render, (Component, object, object, types.NoneType))
@when(presentation.render, (Component, object, object, str))
def render(self, renderer, comp, model):
    """Rendering of a ``Component``
    
    In:
      - ``renderer`` -- the renderer
      - ``comp`` -- the component
      - ``model`` -- the name of the view
      
    Return:
      - the view of the component object
    """
    renderer = renderer.new()   # Create a new renderer of the same class than the current renderer
    renderer.start_rendering(self, model)

    if model == 0:
        model = self.model
        
    output = presentation.render(self(), renderer, self, model)
    return renderer.end_rendering(output)

@presentation.init_for(Component)
def init_for(self, url, comp, http_method, request):
    """Initialisation from an url
    
    In:
      - ``url`` -- rest of the url to process
      - ``comp`` -- the component
      - ``http_method`` -- the HTTP method
      - ``request`` -- the complete Request object
      
    Return:
      - ``presentation.NOT_FOUND`` if the url is invalid, else ``None``
    """    
    presentation.init(self(), url, self, http_method, request)

# -----------------------------------------------------------------------------------------------------

class Task:
    """A ``Task`` encapsulated a simple method. A ``task`` is typically used to
    manage other components by calling them.
    
    .. warning::
    
       A ``Task`` is an object, not a component: you must wrap it into a ``Component()`` to use it.
    """
    
    def _go(self, comp):
        # If I was not called by an other component (I'am the root component),
        # I call forever my ``go()`` method
        if comp._channel is None:
            while True:
                self.go(comp)

        # Else, answer with the return of the ``go`` method
        comp.answer(self.go(comp))

    def go(self, comp):
        raise BaseException('AbstractMethod')
                        
@presentation.render_for(Task)
def render(self, renderer, comp, *args):
    return presentation.render(self._go, renderer, comp, *args)

# -----------------------------------------------------------------------------------------------------

@when(presentation.render, (types.FunctionType,))
@when(presentation.render, (types.MethodType,))
def render(f, renderer, comp, *args):
    call_wrapper(f, comp)
    return comp.render(renderer.parent)
