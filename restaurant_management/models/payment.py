from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class RestaurantPayment(models.Model):
    _name = "restaurant.payment"
    _description = "Restaurant Payment"
    _order = "payment_date desc, id desc"

    # 1. Payment Reference
    name = fields.Char(
        string="Payment Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )

    # 2. Related Order
    order_id = fields.Many2one(
        comodel_name="restaurant.order",
        string="Order",
        required=True,
        ondelete="restrict",
        domain=[("state", "!=", "cancelled")],
    )

    # 3. Customer from the selected Order
    customer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        related="order_id.customer_id",
        store=True,
        readonly=True,
    )

    # 4. Payment Date
    payment_date = fields.Datetime(
        string="Payment Date",
        required=True,
        default=fields.Datetime.now,
    )

    # 5. Payment Amount
    amount = fields.Float(
        string="Amount",
        required=True,
        digits=(16, 2),
    )

    # 6. Payment Method
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

    # 7. Transaction or Receipt Reference
    reference = fields.Char(
        string="Transaction Reference",
    )

    # 8. Payment Status
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="draft",
    )

    # 9. Generate Payment Reference Automatically
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "restaurant.payment"
                    ) or "New"
                )

        return super().create(vals_list)

    # 10. Payment Amount Must Be Greater Than Zero
    @api.constrains("amount")
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(
                    _("Payment amount must be greater than zero.")
                )

    # 11. Prevent Total Posted Payments from Exceeding Order Total
    @api.constrains("amount", "order_id", "state")
    def _check_payment_amount(self):
        for payment in self:
            if payment.state != "posted" or not payment.order_id:
                continue

            other_payments = self.search([
                ("order_id", "=", payment.order_id.id),
                ("state", "=", "posted"),
                ("id", "!=", payment.id),
            ])

            total_paid = (
                sum(other_payments.mapped("amount"))
                + payment.amount
            )

            order_total = payment.order_id.total_amount

            if float_compare(
                total_paid,
                order_total,
                precision_digits=2,
            ) > 0:
                raise ValidationError(
                    _(
                        "Total payments cannot exceed the total "
                        "amount of order %s."
                    ) % payment.order_id.display_name
                )

    # 12. Confirm Payment
    def action_post(self):
        for payment in self:
            if payment.state != "draft":
                raise UserError(
                    _("Only draft payments can be posted.")
                )

            if payment.order_id.state in ("draft", "cancelled"):
                raise UserError(
                    _(
                        "You cannot post a payment for a draft "
                        "or cancelled order."
                    )
                )

        self.write({"state": "posted"})
        return True

    # 13. Cancel Payment
    def action_cancel(self):
        for payment in self:
            if payment.state != "posted":
                raise UserError(
                    _("Only posted payments can be cancelled.")
                )

        self.write({"state": "cancelled"})
        return True

    # 14. Reset Cancelled Payment to Draft
    def action_draft(self):
        for payment in self:
            if payment.state != "cancelled":
                raise UserError(
                    _("Only cancelled payments can be reset to draft.")
                )

        self.write({"state": "draft"})
        return True