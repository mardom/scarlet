import autograd.numpy as np

from .frame import Frame
from .model import Model
from .parameter import Parameter, relative_step
from .constraint import PositivityConstraint
from .bbox import Box, overlapped_slices


class Component(Model):
    """A single component in a blend.

    This class acts as base for building models from parameters.

    Parameters
    ----------
    frame: `~scarlet.Frame`
        Characterization of the model
    parameters: list of `~scarlet.Parameter`
    children: list of `~scarlet.Model`
        Subordinate models.
    bbox: `~scarlet.Box`
        Bounding box of this model
    """

    def __init__(self, frame, *parameters, children=None, bbox=None):

        assert isinstance(frame, Frame)
        if bbox is None:
            bbox = frame.bbox
        assert isinstance(bbox, Box)
        self._bbox = bbox  # don't use th setter bc frame isn't set yet
        self.frame = frame

        super().__init__(*parameters, children=children)

    @property
    def bbox(self):
        """Hyper-spectral bounding box of this model
        """
        return self._bbox

    @bbox.setter
    def bbox(self, b):
        """Sets the bounding box of this component.

        Parameters
        ----------
        b: `~scarlet.Box`
            New bounding box of this model
        """
        if b is None:
            b = self._frame.bbox
        self._bbox = b

        self._model_frame_slices, self._model_slices = overlapped_slices(
            self._frame.bbox, self._bbox
        )

    @property
    def frame(self):
        """Hyper-spectral characteristics is this model
        """
        return self._frame

    @frame.setter
    def frame(self, f):
        """Sets the frame for this component.

        Parameters
        ----------
        f: `~scarlet.Frame`
            New frame of the model
        """
        self._frame = f
        self._model_frame_slices, self._model_slices = overlapped_slices(
            self._frame.bbox, self._bbox
        )

    def model_to_frame(self, frame=None, model=None):
        """Project a model into a frame


        Parameters
        ----------
        model: array
            Image of the model to project.
            This must be the same shape as `self.bbox`.
            If `model` is `None` then `self.get_model()` is used.
        frame: `~scarlet.frame.Frame`
            The frame to project the model into.
            If `frame` is `None` then the model is projected
            into `self.model_frame`.

        Returns
        -------
        projected_model: array
            (Channels, Height, Width) image of the model
        """
        # Use the current model by default
        if model is None:
            model = self.get_model()
        # Use the full model frame by default
        if frame is None or frame == self.frame:
            frame = self.frame
            frame_slices = self._model_frame_slices
            model_slices = self._model_slices
        else:
            frame_slices, model_slices = overlapped_slices(frame.bbox, self.bbox)

        if hasattr(frame, "dtype"):
            dtype = frame.dtype
        else:
            dtype = model.dtype
        result = np.zeros(frame.shape, dtype=dtype)
        result[frame_slices] = model[model_slices]
        return result


class FactorizedComponent(Component):
    """A single component in a blend.

    Uses the non-parametric factorization sed x morphology.

    Parameters
    ----------
    frame: `~scarlet.Frame`
        The spectral and spatial characteristics of the full model.
    bbox: `~scarlet.Box`
        Hyper-spectral bounding box of this component.
    spectrum: `~scarlet.Spectrum`
        Parameterization of the spectrum
    morphology: `~scarlet.Morphology`
        Parameterization of the morphology.
    """

    def __init__(self, frame, spectrum, morphology):
        from .spectrum import Spectrum

        assert isinstance(spectrum, Spectrum)

        from .morphology import Morphology

        assert isinstance(morphology, Morphology)

        bbox = spectrum.bbox @ morphology.bbox

        super().__init__(frame, children=[spectrum, morphology], bbox=bbox)

    def get_model(self, *parameters, frame=None):
        """Get the model for this component.

        Parameters
        ----------
        parameters: tuple of optimimzation parameters

        frame: `~scarlet.frame.Frame`
            Frame to project the model into. If `frame` is `None`
            then the model contained in `bbox` is returned.

        Returns
        -------
        model: array
            (Channels, Height, Width) image of the model
        """
        spectrum, morphology = self.get_models_of_children(*parameters)
        model = spectrum[:, None, None] * morphology[None, :, :]

        # project the model into frame (if necessary)
        if frame is not None:
            model = self.model_to_frame(frame, model)
        return model


class CubeComponent(Component):
    """A single component in a blend.

    Uses full cube parameterization.

    Parameters
    ----------
    frame: `~scarlet.Frame`
        The spectral and spatial characteristics of this component.
    cube: `~scarlet.Parameter`
        3D array (C, Height, Width) of the initial data cube.
    bbox: `~scarlet.Box`
        Hyper-spectral bounding box of this component.
    """

    def __init__(self, frame, cube, bbox=None):
        if isinstance(cube, Parameter):
            assert cube.name == "cube"
        else:
            constraint = PositivityConstraint()
            cube = Parameter(
                cube, name="cube", step=relative_step, constraint=constraint
            )
        super().__init__(frame, cube, bbox=bbox)

    def get_model(self, *parameters, frame=None):
        model = self.get_parameter(0, *parameters)

        if frame is not None:
            model = self.model_to_frame(frame, model)
        return model


class CombinedComponent(Component):
    def __init__(self, components, operation="add", check_boxes=True):

        assert len(components)
        frame = components[0].frame
        box = components[0].bbox
        # all children need to have the same bbox for simple autogradable combinations
        for c in components:
            assert isinstance(c, Component)
            assert c.frame is frame
            if check_boxes:
                assert c.bbox == box

        super().__init__(frame, children=components, bbox=box)

        assert operation in ["add", "multiply"]
        self.operation = operation

    def get_model(self, *parameters, frame=None):
        # boxed models
        models = self.get_models_of_children(*parameters, frame=None)
        model = models[0]
        if self.operation == "add":
            for model_ in models[1:]:
                model += model_
        elif self.operation == "multiply":
            for model_ in models[1:]:
                model *= model_

        if frame is not None:
            model = self.model_to_frame(frame, model)
        return model
