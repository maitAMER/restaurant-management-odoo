from odoo import fields, models
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RestaurantPaymentSplitLine(models.Model):
    _name = "restaurant.payment.split.line"
    _description = "Restaurant Payment Split Line"

    payment_id = fields.Many2one(
        comodel_name="restaurant.payment",
        string="Payment",
        required=True,
        ondelete="cascade",
    )

    method = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("wallet", "Wallet"),
            ("online", "Online Payment"),
        ],
        string="Payment Method",
        required=True,
    )

    amount = fields.Float(
        string="Amount",
        required=True,
        digits=(16, 2),
    )
    @api.constrains("payment_id", "method")
    def _check_unique_payment_method(self):
        for line in self:
            if not line.payment_id or not line.method:
                continue

            other_lines = line.payment_id.split_line_ids.filtered(
                lambda other: (
                    other.id != line.id
                    and other.method == line.method
                )
            )

            if other_lines:
                raise ValidationError(
                    "You cannot use the same payment method "
                    "more than once in a split payment."
                )