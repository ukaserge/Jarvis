from typing import Type

from src.database.connection.abstract_database_connection import Schema, Model, AbstractDataBaseConnection
from src.database.schemas.shopping_list import ShoppingListSchema, shopping_list_to_schema, schema_to_shopping_list
from src.models.shopping_list import ShoppingListItem


class ShoppingListInterface(AbstractDataBaseConnection[ShoppingListItem, ShoppingListSchema]):
    @staticmethod
    def schema_to_model(model_schema: Schema) -> Model:
        return schema_to_shopping_list(model_schema)

    @staticmethod
    def model_to_schema(model: Model) -> Schema:
        return shopping_list_to_schema(model)

    @staticmethod
    def get_model_id(model: ShoppingListItem) -> int:
        return model.id

    @staticmethod
    def get_model_type() -> Type[Model]:
        return ShoppingListItem

    @staticmethod
    def get_schema_type() -> Type[Schema]:
        return ShoppingListSchema

    def __int__(self) -> None:
        super().__init__()
        from src.database.tables.shoppinglist import create_tables
        create_tables(self.engine)