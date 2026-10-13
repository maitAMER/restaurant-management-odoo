# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # Shown as independent checkboxes under the "Restaurant"
    # section of the user form (see views/res_users_views.xml).
    is_restaurant_cashier = fields.Boolean(
        string="Restaurant Cashier",
        compute="_compute_restaurant_groups",
        inverse="_inverse_restaurant_cashier",
    )
    is_restaurant_shift_manager = fields.Boolean(
        string="Shift Manager",
        compute="_compute_restaurant_groups",
        inverse="_inverse_restaurant_shift_manager",
    )

    @api.depends("groups_id")
    def _compute_restaurant_groups(self):
        cashier = self.env.ref(
            "restaurant_management.group_restaurant_cashier"
        )
        manager = self.env.ref(
            "restaurant_management.group_shift_manager"
        )
        for user in self:
            user.is_restaurant_cashier = cashier in user.groups_id
            user.is_restaurant_shift_manager = manager in user.groups_id

    def _inverse_restaurant_cashier(self):
        cashier = self.env.ref(
            "restaurant_management.group_restaurant_cashier"
        )
        for user in self:
            if user.is_restaurant_cashier:
                user.groups_id = [(4, cashier.id)]
            else:
                user.groups_id = [(3, cashier.id)]

    def _inverse_restaurant_shift_manager(self):
        manager = self.env.ref(
            "restaurant_management.group_shift_manager"
        )
        for user in self:
            if user.is_restaurant_shift_manager:
                user.groups_id = [(4, manager.id)]
            else:
                user.groups_id = [(3, manager.id)]
