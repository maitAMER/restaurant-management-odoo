from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RestaurantPaymentSplitLine(models.Model):
    _name = "restaurant.payment.split.line"
    _description = "Restaurant Payment Split Line"
    _order = "id"

    payment_id = fields.Many2one(
        comodel_name="restaurant.payment",
        string="Payment",
        required=True,
        ondelete="cascade",
        index=True,
    )

    method = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("wallet", "Wallet"),
            ("on_account", "On Account"),
        ],
        string="Payment Method",
        required=True,
        default="cash",
    )

    amount = fields.Float(
        string="Amount",
        required=True,
        digits=(16, 2),
    )

    @api.constrains("method", "payment_id")
    def _check_unique_payment_method(self):
        for line in self:
            if not line.payment_id or not line.method:
                continue

            duplicate = self.search([
                ("payment_id", "=", line.payment_id.id),
                ("method", "=", line.method),
                ("id", "!=", line.id),
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    _(
                        "You cannot use the same payment method "
                        "more than once in a split payment."
                    )
                )

    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(
                    _("Split payment amount must be greater than zero.")
                )