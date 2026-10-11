from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RestaurantPaymentSplitLine(models.Model):
    _name = "restaurant.payment.split.line"
    _description = "Restaurant Payment Split Line"
    _order = "id"

    # Link to the main Payment
    payment_id = fields.Many2one(
        comodel_name="restaurant.payment",
        string="Payment",
        required=True,
        ondelete="cascade",
        index=True,
    )

    # Payment Method for this part of the invoice
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

    # Amount paid using this method
    amount = fields.Float(
        string="Amount",
        required=True,
        digits=(16, 2),
    )

    # Optional Transaction Reference
    reference = fields.Char(
        string="Transaction Reference",
    )

    # Each split amount must be greater than zero
    @api.constrains("amount")
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(
                    _("Split payment amount must be greater than zero.")
                )

    @api.constrains("method", "reference")
    def _check_transaction_reference(self):
        for line in self:
            requires_reference = line.method in (
                "card",
                "bank_transfer",
                "wallet",
            )

            if requires_reference and not line.reference:
                raise ValidationError(
                    _("Transaction Reference is required for this payment method.")
                )

            if line.reference:
                # Check other split payment lines
                existing_line = self.search([
                    ("reference", "=", line.reference),
                    ("id", "!=", line.id),
                ], limit=1)

                if existing_line:
                    raise ValidationError(
                        _("This Transaction Reference already exists.")
                    )

                # Check main payment records
                existing_payment = self.env["restaurant.payment"].search([
                    ("reference", "=", line.reference),
                ], limit=1)

                if existing_payment:
                    raise ValidationError(
                        _("This Transaction Reference already exists in a payment.")
                    )