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
        domain=[
            ("state", "!=", "cancelled"),
            ("payment_ids", "=", False),
        ],
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
    # Automatically gets the total amount from the selected order
    amount = fields.Float(
        string="Amount",
        compute="_compute_amount",
        store=True,
        digits=(16, 2),
        readonly=True,
    )

    @api.depends("order_id", "order_id.total_amount")
    def _compute_amount(self):
        for payment in self:
            if payment.order_id:
                payment.amount = payment.order_id.total_amount
            else:
                payment.amount = 0.0

        # 6. Split Payment Lines
    split_line_ids = fields.One2many(
        comodel_name="restaurant.payment.split.line",
        inverse_name="payment_id",
        string="Split Payment",
    )

    # Total of all split lines
    split_total = fields.Float(
        string="Split Total",
        compute="_compute_split_summary",
        digits=(16, 2),
    )

    # Absolute difference between split total and payment amount
    split_difference = fields.Float(
        string="Difference",
        compute="_compute_split_summary",
        digits=(16, 2),
    )

    # Split Payment Validation Status
    split_status = fields.Selection(
        selection=[
            ("not_used", "Not Used"),
            ("less", "Less than Payment Amount"),
            ("greater", "Greater than Payment Amount"),
            ("matched", "Matched"),
        ],
        string="Split Status",
        compute="_compute_split_summary",
    )
    # Payment Type Selection
    standard_payment = fields.Boolean(
        string="Standard Payment",
        default=True,
    )

    split_payment = fields.Boolean(
        string="Split Payment",
        default=False,
    )

    @api.depends(
        "amount",
        "split_line_ids.amount",
    )
    def _compute_split_summary(self):
        for payment in self:
            if not payment.split_line_ids:
                payment.split_total = 0.0
                payment.split_difference = 0.0
                payment.split_status = "not_used"
                continue

            total = sum(payment.split_line_ids.mapped("amount"))

            payment.split_total = total
            payment.split_difference = abs(
                round(total - payment.amount, 2)
            )

            if float_compare(
                total,
                payment.amount,
                precision_digits=2,
            ) < 0:
                payment.split_status = "less"

            elif float_compare(
                total,
                payment.amount,
                precision_digits=2,
            ) > 0:
                payment.split_status = "greater"

            else:
                payment.split_status = "matched"            

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
    # 11. Prevent Multiple Payments for the Same Order
    @api.constrains("order_id")
    def _check_order_payment(self):
        for payment in self:
            if not payment.order_id:
                continue

            existing_payment = self.search([
                ("order_id", "=", payment.order_id.id),
                ("id", "!=", payment.id),
            ], limit=1)

            if existing_payment:
                raise ValidationError(
                    _(
                        "This order already has a payment. "
                        "You cannot create another payment "
                        "for the same order."
                    )
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
                        # Validate Split Payment Total before confirming
            if payment.split_line_ids:
                split_total = sum(
                    payment.split_line_ids.mapped("amount")
                )

                comparison = float_compare(
                    split_total,
                    payment.amount,
                    precision_digits=2,
                )

                difference = abs(
                    round(split_total - payment.amount, 2)
                )

                if comparison < 0:
                    raise UserError(
                        _(
                            "Split total is less than the payment "
                            "amount by %.2f."
                        ) % difference
                    )

                if comparison > 0:
                    raise UserError(
                        _(
                            "Split total exceeds the payment "
                            "amount by %.2f."
                        ) % difference
                    )
                if payment.standard_payment and payment.split_line_ids:
                    raise UserError(
                        _(
                            "You selected Standard Payment. "
                            "Remove the split payment lines before confirming."
                        )
                    )

                if payment.split_payment and not payment.split_line_ids:
                    raise UserError(
                        _("Please add at least one split payment line.")
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

    @api.constrains("method", "reference")
    def _check_transaction_reference(self):
        for payment in self:
            requires_reference = payment.method in (
                "card",
                "bank_transfer",
                "wallet",
            )

            if requires_reference and not payment.reference:
                raise ValidationError(
                    _("Transaction Reference is required for this payment method.")
                )

            if payment.reference:
                existing_payment = self.search([
                    ("reference", "=", payment.reference),
                    ("id", "!=", payment.id),
                ], limit=1)

                if existing_payment:
                    raise ValidationError(
                        _("This Transaction Reference already exists.")
                    )

    @api.onchange("standard_payment")
    def _onchange_standard_payment(self):
        if self.standard_payment:
            self.split_payment = False
        else:
            self.split_payment = True


    @api.onchange("split_payment")
    def _onchange_split_payment(self):
        if self.split_payment:
            self.standard_payment = False
        else:
            self.standard_payment = True


    @api.constrains("standard_payment", "split_payment")
    def _check_payment_type(self):
        for payment in self:
            if payment.standard_payment == payment.split_payment:
                raise ValidationError(
                    _(
                        "Please select either Standard Payment "
                        "or Split Payment, not both."
                    )
                )