"""This module contains the warning category types."""


class MetadataKeyOverwrittenWarning(UserWarning):
    """The warning category for when the metadata mapping provided to a
    field already contains the metadata key for the field type
    metadata.
    """
    pass
