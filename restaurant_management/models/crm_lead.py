from odoo import models, fields, _
from odoo.exceptions import UserError


## task 37

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    order_id = fields.Many2one(
        'restaurant.order',
        string='Order',
        readonly=True,
        copy=False,
    )

    # FIXED: 'restaurant.menu' does not exist, the real model is restaurant.menu.category
    menu_category_id = fields.Many2one(
        'restaurant.menu.category',
        string='Menu Category',
    )

    # FIXED label: avoids duplicate "Customer" label with partner_id
    customer_id = fields.Many2one(
        'restaurant.customer',
        string='Restaurant Customer',
        copy=False,
    )

    lead_source = fields.Selection(
        [
            ('website', 'Website'),
            ('api', 'API'),
            ('manual', 'Manual'),
        ],
        string='Lead Source',
        default='manual',
        required=True,
    )

    ## task 38

    def action_convert_to_order(self):
        self.ensure_one()
        lead = self

        # Prevent duplicate conversion
        if lead.order_id:
            raise UserError(_("This lead has already been converted to an order."))

        # Get customer information from the lead
        email = lead.email_from or lead.partner_id.email or False
        customer_name = lead.contact_name or lead.partner_id.name or lead.name

        # Find an existing customer by email
        customer = self.env['restaurant.customer']
        if email:
            customer = customer.search([('email', '=ilike', email)], limit=1)

        # Create customer if it does not exist
        if not customer:
            customer_vals = {'name': customer_name}
            if email:
                customer_vals['email'] = email
            if lead.phone:
                customer_vals['phone'] = lead.phone
            if 'mobile' in lead._fields and lead.mobile:
                customer_vals['mobile'] = lead.mobile
            customer = self.env['restaurant.customer'].create(customer_vals)

        order = self.env['restaurant.order'].create({
            'customer_id': customer.id,
            'order_type': 'dine_in',
            'state': 'draft',
        })

        # Link customer and order to the lead
        lead.write({
            'customer_id': customer.id,
            'order_id': order.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Restaurant Order'),
            'res_model': 'restaurant.order',
            'view_mode': 'form',
            'res_id': order.id,
            'target': 'current',
        }