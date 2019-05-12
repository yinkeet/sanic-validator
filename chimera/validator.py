from functools import wraps

from bson.errors import InvalidId
from bson.objectid import ObjectId
from cerberus import Validator
from sanic.exceptions import InvalidUsage, NotFound
from sanic.request import File, Request


class CustomValidator(Validator):
    def __init__(self, request=None, *args, **kwargs):
        super(CustomValidator, self).__init__(*args, **kwargs)
        self.request = request

    # Types
    def _validate_type_object_id(self, value):
        return isinstance(value, ObjectId)
    
    def _validate_type_file(self, value):
        return isinstance(value, File)

    # Checks
    def _check_with_object_id_validator(self, field, value):
        try:
            ObjectId(value)
        except InvalidId as _error:
            self._error(field, "invalid id")

    # Coerce
    def _normalize_coerce_json(self, value):
        from json import loads
        return loads(value)

    def _normalize_coerce_first(self, value):
        return value[0]

    def _normalize_coerce_object_id(self, value):
        return ObjectId(value)

    def _normalize_coerce_boolean(self, value):
        return value.lower() in ('true', '1')

    def _normalize_coerce_integer(self, value):
        return int(value)

    # Validates
    def _validate_allowed_path(self, allowed_path, field, value):
        if isinstance(allowed_path, str):
            allowed_path = [allowed_path]
        
        if value not in allowed_path:
            if self.request:
                raise NotFound('Requested URL {} not found'.format(self.request.path))
            else:
                raise NotFound('Requested URL not found')

    def _validate_allowed_content_type(self, allowed_content_type, field, value):
        if value.type not in allowed_content_type:
            self._error(field, "Content type not allowed")

    # Default setters
    def _normalize_default_setter_array_wrap(self, document):
        return [document]

    def _normalize_default_setter_timestamp(self, document):
        from time import time
        return [str(int(time()))]

class ValidatePath(object):
    def __init__(self, schema: dict):
        self.schema = schema

    def __call__(self, function):
        @wraps(function)
        async def wrapper(request, *args, **kwargs):
            validator = CustomValidator(request=request, schema=self.schema, allow_unknown=True)
            
            if not validator.validate(kwargs):
                raise InvalidUsage(validator.errors)

            return await function(request, *args, **validator.document)

        return wrapper

class ValidateRequest(object):
    def __init__(self, schema: dict, request_property: str):
        self.schema = schema
        self.request_property = request_property

    def __call__(self, function):
        @wraps(function)
        async def wrapper(request, *args, **kwargs):
            validator = CustomValidator(request=request, schema=self.schema, purge_unknown=True)
            
            document = getattr(request, self.request_property, {})
            document = dict(document) if document else {}
            
            if not validator.validate(document):
                raise InvalidUsage(validator.errors)

            validated = kwargs.get('validated', {})
            validated[self.request_property] = validator.document
            kwargs['validated'] = validated

            return await function(request, *args, **kwargs)

        return wrapper