from odoo import fields, models


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

    reference = fields.Char(
        string="Transaction Reference",
    )