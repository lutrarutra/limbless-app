from typing import Optional, Literal

from flask import Response, url_for, flash
from wtforms import StringField, SelectField, FloatField, FormField
from wtforms.validators import DataRequired, Length, Optional as OptionalValidator

from flask_htmx import make_response

from limbless_db import models
from limbless_db.categories import PoolStatus, PoolType

from ... import logger, db  # noqa F401
from ..SearchBar import OptionalSearchBar
from ..HTMXFlaskForm import HTMXFlaskForm


class PoolForm(HTMXFlaskForm):
    _template_path = "forms/pool.html"
    _form_label = "pool_form"

    name = StringField("Pool Name", validators=[DataRequired(), Length(min=4, max=models.Pool.name.type.length)])
    pool_type = SelectField("Pool Type", choices=PoolType.as_selectable(), coerce=int)
    num_m_reads_requested = FloatField("Number of M Reads Requested", validators=[OptionalValidator()])
    status = SelectField("Status", choices=PoolStatus.as_selectable(), coerce=int)
    contact = FormField(OptionalSearchBar, "Select Existing Contact")
    contact_name = StringField("Contact Name", validators=[OptionalValidator(), Length(max=models.Contact.name.type.length)])
    contact_email = StringField("Contact Email", validators=[OptionalValidator(), Length(max=models.Contact.email.type.length)])
    contact_phone = StringField("Contact Phone", validators=[OptionalValidator(), Length(max=models.Contact.phone.type.length)])

    def __init__(self, form_type: Literal["edit", "create"], formdata=None):
        super().__init__(formdata=formdata)
        self.form_type = form_type
        self._context["form_type"] = form_type

    def validate(self, pool: Optional[models.Pool]) -> bool:
        if not super().validate():
            return False

        if self.contact.selected.data is None and not self.contact_name.data:
            self.contact_name.errors = ("Select an existing contact or provide a name",)
            return False
        
        if self.contact.selected.data is None and not self.contact_email.data:
            self.contact_email.errors = ("Select an existing contact or provide a email",)
            return False
        
        pool_type = PoolType.get(self.pool_type.data)
        if self.form_type == "edit":
            if pool is None:
                raise Exception("Pool not passed as argument for edit form")
            if pool_type != pool.type:
                self.pool_type.errors = ("Pool type cannot be changed, please create a new pool",)
                return False

        return True

    def prepare(self, pool: models.Pool):
        self.name.data = pool.name
        self.pool_type.data = pool.type.id
        self.status.data = pool.status_id
        self.num_m_reads_requested.data = pool.num_m_reads_requested
        self.contact_name.data = pool.contact.name
        self.contact_email.data = pool.contact.email
        self.contact_phone.data = pool.contact.phone
        self._context["pool"] = pool

    def __edit_existing_pool(self, pool_id: int) -> models.Pool:
        if (pool := db.get_pool(pool_id)) is None:
            raise ValueError(f"Pool {pool_id} not found")
            
        pool.name = self.name.data  # type: ignore
        pool.status = PoolStatus.get(self.status.data)
        pool.type = PoolType.get(self.pool_type.data)
        pool.num_m_reads_requested = self.num_m_reads_requested.data
        pool.contact.name = self.contact_name.data  # type: ignore
        pool.contact.email = self.contact_email.data  # type: ignore
        pool.contact.phone = self.contact_phone.data  # type: ignore

        pool = db.update_pool(pool)

        return pool

    def __create_new_pool(self, user: models.User) -> models.Pool:
        if (contact_id := self.contact.selected.data) is not None:
            if (contact := db.get_user(contact_id)) is None:
                logger.error(f"Contact {contact_id} not found")
                raise ValueError(f"Contact {contact_id} not found")
            
        pool_type = PoolType.get(self.pool_type.data)
            
        pool = db.create_pool(
            name=self.name.data,  # type: ignore
            status=PoolStatus.get(self.status.data),
            num_m_reads_requested=self.num_m_reads_requested.data,
            owner_id=user.id,
            pool_type=pool_type,
            contact_name=self.contact_name.data if contact is None else contact.name,  # type: ignore
            contact_email=self.contact_email.data if contact is None else contact.email,  # type: ignore
            contact_phone=self.contact_phone.data  # type: ignore
        )
        return pool
    
    def process_request(self, user: models.User, pool: Optional[models.Pool] = None) -> Response:
        if not self.validate(pool=pool):
            self._context["pool"] = pool
            return self.make_response()
        
        if pool is not None:
            pool = self.__edit_existing_pool(pool.id)
            flash(f"Edited pool {pool.name}", "success")
        else:
            pool = self.__create_new_pool(user)
            flash(f"Created pool {pool.name}", "success")
        
        return make_response(redirect=url_for("pools_page.pool_page", pool_id=pool.id))
        
