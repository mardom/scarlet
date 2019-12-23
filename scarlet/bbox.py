import numpy as np


class Box:
    """Bounding Box for an object

    A Bounding box describes the location of a data unit in the global/model coordinate
    system. It is used to identify spatial and channel overlap and to map from model
    to observed frames and back.

    Parameters
    ----------
    shape: tuple
        Size of the box in depth,height,width
    origin: tuple
        Minimum (z,y,x) value of the box (front low left corner).
    """

    def __init__(self, shape, origin=(0, 0, 0)):
        # bbox always in 3D
        if len(shape) == 2:
            shape = (0, *shape)
        assert len(shape) == 3
        self.shape = shape

        if len(origin) == 2:
            origin = (0, *origin)
        assert len(origin) == 3
        self.origin = origin

    @staticmethod
    def from_image(image):
        """Initialize a box to cover `image`

        Parameters
        ----------
        image: array-like
            2D image

        Returns
        -------
        bbox: `:class:`scarlet.bbox.Box`
            A new box bounded by the image.
        """
        return Box(image.shape)

    @staticmethod
    def from_bounds(front, back, bottom, top, left, right):
        """Initialize a box from its bounds

        Parameters
        ----------
        bottom: int
            Minimum in the y direction.
        top: int
            Maximum in the y direction.
        left: int
            Minimum in the x direction.
        right: int
            Maximum in the x direction.

        Returns
        -------
        bbox: :class:`scarlet.bbox.Box`
            A new box bounded by the input bounds.
        """
        if back < front:
            back, front = front, back
        if top < bottom:
            top, bottom = bottom, top
        if right < left:
            right, left = left, right
        return Box(
            (back - front, top - bottom, right - left), origin=(front, bottom, left)
        )

    @staticmethod
    def from_data(X, min_value=0):
        """Define range of `X` above `min_value`

        Parameters
        ----------
        X: array-like
            Data to threshold
        min_value: float
            Minimum value of the result.

        Returns
        -------
        bbox: :class:`scarlet.bbox.Box`
            Bounding box for the thresholded `X` (bottom, top, left, right)
        """
        sel = X > min_value
        if sel.any():
            nonzero = np.where(sel)
            bounds = []
            for dim in range(len(X.shape)):
                bounds.append(nonzero[dim].min())
                bounds.append(nonzero[dim].max() + 1)
            if len(X.shape) == 2:
                bounds.insert(0, 0)
                bounds.insert(1, 0)
        else:
            bounds = [0] * 6
        return Box.from_bounds(*bounds)

    def contains(self, p):
        """Whether the box cotains a given coordinate `p`
        """
        if len(p) == 2:
            p = (0, *p)

        for d in range(len(self.shape)):
            if p[d] < self.origin[d] or p[d] > self.origin[d] + self.shape[d]:
                return False
        return True

    def slices_for(self, im_or_shape):
        """Slices for `im_or_shape` to be limited to this bounding box.

        Parameters
        ----------
        im_or_shape: array or tuple
            Array or shape of the array to be sliced

        Returns
        -------
        If shape is 2D: `slice_y`, `slice_x`
        If shape is 3: `slice(None)`, `slice_y`, `slice_x`
        """
        if hasattr(im_or_shape, "shape"):
            shape = im_or_shape.shape
        else:
            shape = im_or_shape
        assert len(shape) in [2, 3]

        im_box = Box(shape)
        overlap = self & im_box
        zslice, yslice, xslice = (
            slice(overlap.front, overlap.back),
            slice(overlap.bottom, overlap.top),
            slice(overlap.left, overlap.right),
        )

        if len(shape) == 2:
            return yslice, xslice
        else:
            return zslice, yslice, xslice

    def extract_from(self, image, sub=None):
        """Extract sub-image described by this bbox from image

        Parameters
        ----------
        image: array
            Full image
        sub: array
            Extracted image

        Returns
        -------
        sub: array
        """
        imbox = Box.from_image(image)

        if sub is None:
            if len(image.shape) == 3:
                sub = np.zeros(self.shape)
            else:
                sub = np.zeros(self.shape[1:])
        subbox = Box.from_image(sub)

        # imbox now in the frame of this bbox (i.e. of box)
        imbox -= self.origin
        overlap = imbox & subbox
        sub[overlap.slices_for(sub)] = image[self.slices_for(image)]
        return sub

    def insert_into(self, image, sub):
        """Insert `sub` into `image` according to this bbox

        Inverse operation to :func:`~scarlet.bbox.Box.extract_from`.

        Parameters
        ----------
        image: array
            Full image
        sub: array
            Extracted sub-image

        Returns
        -------
        image: array
        """
        imbox = Box.from_image(image)
        subbox = Box.from_image(sub)

        # imbox now in the frame of this bbox (i.e. of box)
        imbox -= self.origin
        overlap = imbox & subbox
        image[self.slices_for(image)] = sub[overlap.slices_for(sub)]
        return image

    @property
    def C(self):
        """Number of channels in the model
        """
        return self.shape[0]

    @property
    def Ny(self):
        """Number of pixel in the y-direction
        """
        return self.shape[1]

    @property
    def Nx(self):
        """Number of pixels in the x-direction
        """
        return self.shape[2]

    @property
    def front(self):
        """Minimum z value
        """
        return self.origin[0]

    @property
    def bottom(self):
        """Minimum y value
        """
        return self.origin[1]

    @property
    def left(self):
        """Minimum x value
        """
        return self.origin[2]

    @property
    def back(self):
        """Maximum y value
        """
        return self.origin[0] + self.shape[0]

    @property
    def top(self):
        """Maximum y value
        """
        return self.origin[1] + self.shape[1]

    @property
    def right(self):
        """Maximum x value
        """
        return self.origin[2] + self.shape[2]

    def __or__(self, other):
        """Union of two bounding boxes

        Parameters
        ----------
        other: `Box`
            The other bounding box in the union

        Returns
        -------
        result: `Box`
            The smallest rectangular box that contains *both* boxes.
        """
        front = min(self.front, other.front)
        back = max(self.back, other.back)
        bottom = min(self.bottom, other.bottom)
        top = max(self.top, other.top)
        left = min(self.left, other.left)
        right = max(self.right, other.right)
        return Box.from_bounds(front, back, bottom, top, left, right)

    def __and__(self, other):
        """Intersection of two bounding boxes

        If there is no intersection between the two bounding
        boxes then an empty bounding box is returned.

        Parameters
        ----------
        other: `Box`
            The other bounding box in the intersection

        Returns
        -------
        result: `Box`
            The rectangular box that is in the overlap region
            of both boxes.
        """
        front = max(self.front, other.front)
        back = min(self.back, other.back)
        bottom = max(self.bottom, other.bottom)
        top = min(self.top, other.top)
        left = max(self.left, other.left)
        right = min(self.right, other.right)
        return Box.from_bounds(front, back, bottom, top, left, right)

    def __str__(self):
        return "Box({0}..{1}, {2}..{3}, {4}..{5})".format(
            self.front, self.back, self.bottom, self.top, self.left, self.right
        )

    def __repr__(self):
        result = "<Box shape={0}, origin={1}>"
        return result.format(self.shape, self.origin)

    def __iadd__(self, offset):
        self.origin = tuple([a + o for a, o in zip(self.origin, offset)])
        return self

    def __isub__(self, offset):
        self.origin = tuple([a - o for a, o in zip(self.origin, offset)])
        return self

    def __copy__(self):
        return Box(self.shape, offset=self.offset)

    def __eq__(self, other):
        return self.shape == other.shape and self.origin == other.origin
