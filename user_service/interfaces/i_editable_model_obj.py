from abc import ABC, abstractmethod
from typing import Union


class IEditableModelObj(ABC):
    """
    The object has to be a database model.
    """

    @abstractmethod
    def user_can_edit(
        self, object_id: Union[int, str], user_id: Union[int, str]
    ) -> bool:
        """
        check a user can edit a database record.
        object_id is the record id
        user_id is the user id
        """
        pass

    @abstractmethod
    def get_visibility(self, id: Union[int, str]) -> str:
        """
        return the object visibility based on its id.
        """

        pass
