import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RestaurantCustomer(models.Model):
    _name = 'restaurant.customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Restaurant Customer'

    customer_reference = fields.Char(
        string='Customer Reference', readonly=True, copy=False, index=True,
    )
    name = fields.Char(string='Name', required=True, tracking=True)
    image_1920 = fields.Image(string='Customer Image', max_width=1920, max_height=1920)
    customer_type = fields.Selection(
        [('individual', 'Individual'), ('corporate', 'Corporate')],
        string='Customer Type', required=True, default='individual', tracking=True,
    )
    phone = fields.Char(string='Phone', tracking=True)
    mobile = fields.Char(string='Mobile', tracking=True)
    mobile_normalized = fields.Char(compute='_compute_normalized_identifiers', store=True, index=True)
    email = fields.Char(
        string='Email', tracking=True,
        help='Enter a valid email address, for example name@example.com.',
    )
    email_normalized = fields.Char(
        compute='_compute_normalized_identifiers', store=True, index=True,
    )
    address = fields.Text(string='Address', tracking=True)
    date_of_birth = fields.Date(string='Date of Birth')
    loyalty_points = fields.Integer(
        string='Loyalty Points', default=0, readonly=True,
        groups="restaurant_management.group_shift_manager",
    )
    loyalty_transaction_ids = fields.One2many(
        'restaurant.customer.loyalty.transaction', 'customer_id', string='Loyalty History',
    )
    company_tax_id = fields.Char(string='Company Tax ID', tracking=True)
    company_tax_id_normalized = fields.Char(
        compute='_compute_normalized_identifiers', store=True, index=True,
    )
    company_website = fields.Char(string='Company Website')
    contact_person = fields.Char(string='Contact Person', tracking=True)
    contact_person_mobile = fields.Char(string='Contact Person Mobile', tracking=True)
    favorite_items = fields.Many2many(
        'restaurant.menu.item', 'restaurant_customer_menu_favorite_rel',
        'customer_id', 'menu_item_id', string='Favorite Menu Items',
    )
    user_id = fields.Many2one('res.users', string='Related User', ondelete='set null')
    active = fields.Boolean(default=True)
    internal_notes = fields.Text(string='Internal Notes', groups='base.group_system')
    order_ids = fields.One2many(
        'restaurant.order', 'restaurant_customer_id', string='Orders',
    )
    total_spent = fields.Monetary(
        string='Total Spent', compute='_compute_total_spent', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends('order_ids.total_amount', 'order_ids.state')
    def _compute_total_spent(self):
        for customer in self:
            customer.total_spent = sum(
                customer.order_ids.filtered(lambda order: order.state == 'completed')
                .mapped('total_amount')
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('customer_reference'):
                vals['customer_reference'] = (
                    self.env['ir.sequence'].next_by_code('restaurant.customer') or '/'
                )
        return super().create(vals_list)

    def copy_data(self, default=None):
        # A duplicate is a new customer, so unique identifiers must be entered
        # again instead of being copied from the original record.
        default = dict(default or {})
        default.setdefault('email', False)
        default.setdefault('mobile', False)
        default.setdefault('company_tax_id', False)
        return super().copy_data(default)

    @api.depends('mobile', 'email', 'company_tax_id')
    def _compute_normalized_identifiers(self):
        for customer in self:
            customer.mobile_normalized = re.sub(r'\D', '', customer.mobile or '') or False
            customer.email_normalized = (customer.email or '').strip().casefold() or False
            customer.company_tax_id_normalized = re.sub(
                r'[^A-Za-z0-9]', '', customer.company_tax_id or '',
            ).upper() or False

    @api.constrains('mobile', 'customer_type')
    def _check_individual_mobile_is_unique(self):
        for customer in self:
            if customer.customer_type != 'individual' or not customer.mobile_normalized:
                continue
            duplicate = self.search([
                ('id', '!=', customer.id),
                ('customer_type', '=', 'individual'),
                ('mobile_normalized', '=', customer.mobile_normalized),
            ], limit=1)
            if duplicate:
                raise ValidationError('This mobile number is already used by another individual customer.')

    @api.constrains('email')
    def _check_email_format_and_uniqueness(self):
        for customer in self:
            email = (customer.email or '').strip()
            if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
                raise ValidationError(
                    'Enter a valid email address, for example name@example.com.'
                )
            if not customer.email_normalized:
                continue
            duplicate = self.search([
                ('id', '!=', customer.id),
                ('email_normalized', '=', customer.email_normalized),
            ], limit=1)
            if duplicate:
                raise ValidationError('This email address is already used by another customer.')

    @api.constrains('company_tax_id', 'customer_type')
    def _check_corporate_tax_id_is_unique(self):
        for customer in self:
            if customer.customer_type != 'corporate' or not customer.company_tax_id_normalized:
                continue
            duplicate = self.search([
                ('id', '!=', customer.id),
                ('customer_type', '=', 'corporate'),
                ('company_tax_id_normalized', '=', customer.company_tax_id_normalized),
            ], limit=1)
            if duplicate:
                raise ValidationError('This tax ID is already used by another corporate customer.')

    def action_open_loyalty_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('restaurant_management.group_shift_manager'):
            raise AccessError('Only Shift Managers can adjust loyalty points.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Adjust Loyalty Points',
            'res_model': 'restaurant.customer.loyalty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_customer_id': self.id},
        }


class RestaurantCustomerLoyaltyTransaction(models.Model):
    _name = 'restaurant.customer.loyalty.transaction'
    _description = 'Customer Loyalty Transaction'
    _order = 'date desc, id desc'

    customer_id = fields.Many2one(
        'restaurant.customer', string='Customer', required=True, ondelete='cascade',
    )
    source_order_id = fields.Many2one(
        'restaurant.order', string='Earned From Order', ondelete='set null',
    )
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    points_delta = fields.Integer(string='Points Change', required=True)
    balance_after = fields.Integer(string='Balance After', required=True)
    reason = fields.Char(string='Reason', required=True)

    _sql_constraints = [
        (
            'source_order_unique',
            'unique(source_order_id)',
            'An order can award loyalty points only once.',
        ),
    ]

    def unlink(self):
        customers = self.mapped('customer_id')
        transactions_to_keep = self.env['restaurant.customer.loyalty.transaction'].sudo()

        for customer in customers:
            remaining = transactions_to_keep.search([
                ('customer_id', '=', customer.id),
                ('id', 'not in', self.ids),
            ], order='date, id')
            balance = 0
            for transaction in remaining:
                balance += transaction.points_delta
                if balance < 0:
                    raise UserError(
                        'These history lines cannot be deleted because the remaining '
                        'transactions would create a negative point balance.'
                    )

        result = super().unlink()
        for customer in customers:
            remaining = transactions_to_keep.search(
                [('customer_id', '=', customer.id)], order='date, id',
            )
            balance = 0
            for transaction in remaining:
                balance += transaction.points_delta
                transaction.balance_after = balance
            customer.sudo().write({'loyalty_points': balance})
        return result


class RestaurantCustomerLoyaltyWizard(models.TransientModel):
    _name = 'restaurant.customer.loyalty.wizard'
    _description = 'Adjust Customer Loyalty Points'

    customer_id = fields.Many2one('restaurant.customer', required=True, readonly=True)
    points_delta = fields.Integer(
        string='Points Change', required=True,
        help='Use a positive number to add points or a negative number to redeem them.',
    )
    reason = fields.Char(string='Reason', required=True)

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('restaurant_management.group_shift_manager'):
            raise AccessError('Only Shift Managers can adjust loyalty points.')
        if not self.points_delta:
            raise UserError('Enter a points change greater than or less than zero.')
        new_balance = self.customer_id.loyalty_points + self.points_delta
        if new_balance < 0:
            raise ValidationError('The loyalty points balance cannot be less than zero.')

        self.customer_id.write({'loyalty_points': new_balance})
        self.env['restaurant.customer.loyalty.transaction'].create({
            'customer_id': self.customer_id.id,
            'points_delta': self.points_delta,
            'balance_after': new_balance,
            'reason': self.reason,
        })
        return {'type': 'ir.actions.client', 'tag': 'reload'}
