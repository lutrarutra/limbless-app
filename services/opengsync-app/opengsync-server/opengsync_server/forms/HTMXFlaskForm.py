from typing import Optional, Any

from flask import Response, render_template
from flask_htmx import make_response
from flask_wtf import FlaskForm
from werkzeug.datastructures import ImmutableMultiDict

from ..tools import classproperty


class HTMXFlaskForm(FlaskForm):
    _template_path: Optional[str] = None
    _form_label: str = "form"

    def __init__(self, formdata: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(formdata=ImmutableMultiDict(formdata), **kwargs)
        self.formdata = formdata if formdata is not None else dict()
        self._context = {}

    def process_request(self) -> Response:
        raise NotImplementedError("You must implement this method in your subclass.")

    @classproperty
    def template_path(self) -> str:
        if self._template_path is None:
            raise NotImplementedError("You must implement this property in your subclass.")
        return self._template_path
    
    @classproperty
    def form_label(self) -> str:
        return self._form_label

    def make_response(self, **context) -> Response:
        context = context | {self._form_label: self} | self._context
        return make_response(
            render_template(
                self.template_path, **context
            )
        )