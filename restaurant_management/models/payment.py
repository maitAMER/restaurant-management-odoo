from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class RestaurantPayment(models.Model):
    _name = "restaurant.payment"
    _description = "Restaurant Payment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "payment_date desc, id desc"

    # =========================
    # BASIC INFORMATION
    # =========================

    name = fields.Char(
        string="Payment Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        tracking=True,
    )

    order_id = fields.Many2one(
        comodel_name="restaurant.order",
        string="Order",
        required=True,
        ondelete="restrict",
        domain=[
            ("state", "!=", "cancelled"),
            ("payment_ids", "=", False),
        ],
        tracking=True,
    )

    customer_id = fields.Many2one(
        comodel_name="restaurant.customer",
        string="Customer",
        related="order_id.restaurant_customer_id",
        store=True,
        readonly=True,
    )

    payment_date = fields.Datetime(
        string="Payment Date",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )

    # =========================
    # AMOUNTS
    # =========================

    amount = fields.Float(
        string="Order Amount",
        compute="_compute_amount",
        store=True,
        readonly=True,
        digits=(16, 2),
    )

    tip_amount = fields.Float(
        string="Tip",
        default=0.0,
        digits=(16, 2),
    )

    late_fee = fields.Float(
        string="Late Fee",
        default=0.0,
        digits=(16, 2),
    )

    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
        readonly=True,
        digits=(16, 2),
    )

    @api.depends("order_id", "order_id.total_amount")
    def _compute_amount(self):
        for payment in self:
            payment.amount = (
                payment.order_id.total_amount
                if payment.order_id
                else 0.0
            )

    @api.depends("amount", "tip_amount", "late_fee")
    def _compute_total_amount(self):
        for payment in self:
            payment.total_amount = (
                payment.amount
                + payment.tip_amount
                + payment.late_fee
            )

    @api.constrains("tip_amount", "late_fee")
    def _check_extra_amounts(self):
        for payment in self:
            if payment.tip_amount < 0:
                raise ValidationError(
                    _("Tip cannot be negative.")
                )

            if payment.late_fee < 0:
                raise ValidationError(
                    _("Late Fee cannot be negative.")
                )

    # =========================
    # PAYMENT METHOD
    # =========================

    payment_type = fields.Selection(
        selection=[
            ("single", "Single Payment"),
            ("split", "Split Payment"),
        ],
        string="Payment Type",
        required=True,
        default="single",
        tracking=True,
    )

    # =========================
# PAYMENT TYPE CHECKBOXES
# =========================

    standard_payment = fields.Boolean(
        string="Standard Payment",
        compute="_compute_payment_type_checkboxes",
        inverse="_inverse_standard_payment",
    )

    split_payment = fields.Boolean(
        string="Split Payment",
        compute="_compute_payment_type_checkboxes",
        inverse="_inverse_split_payment",
    )


    @api.depends("payment_type")
    def _compute_payment_type_checkboxes(self):
        for payment in self:
            payment.standard_payment = payment.payment_type == "single"
            payment.split_payment = payment.payment_type == "split"


    def _inverse_standard_payment(self):
        for payment in self:
            if payment.standard_payment:
                payment.payment_type = "single"


    def _inverse_split_payment(self):
        for payment in self:
            if payment.split_payment:
                payment.payment_type = "split"

    method = fields.Selection(
        selection=[
            ("cash", "Cash"),
            ("card", "Card"),
            ("bank_transfer", "Bank Transfer"),
            ("wallet", "Wallet"),
            ("online", "Online Payment"),
        ],
        string="Payment Method",
        tracking=True,
    )

    # =========================
    # SPLIT PAYMENT
    # =========================

    split_line_ids = fields.One2many(
        comodel_name="restaurant.payment.split.line",
        inverse_name="payment_id",
        string="Split Payment Lines",
        copy=True,
    )

    split_total = fields.Float(
        string="Split Total",
        compute="_compute_split_summary",
        store=True,
        digits=(16, 2),
    )

    split_difference = fields.Float(
        string="Remaining Amount",
        compute="_compute_split_summary",
        store=True,
        digits=(16, 2),
    )

    split_status = fields.Selection(
        selection=[
            ("empty", "No Split Lines"),
            ("incomplete", "Amount Incomplete"),
            ("excess", "Amount Exceeds Total"),
            ("balanced", "Balanced"),
        ],
        string="Split Status",
        compute="_compute_split_summary",
        store=True,
    )

    @api.depends(
        "split_line_ids.amount",
        "total_amount",
        "payment_type",
    )
    def _compute_split_summary(self):
        for payment in self:
            split_total = sum(
                payment.split_line_ids.mapped("amount")
            )

            payment.split_total = split_total
            payment.split_difference = (
                payment.total_amount - split_total
            )

            if not payment.split_line_ids:
                payment.split_status = "empty"

            elif float_compare(
                split_total,
                payment.total_amount,
                precision_digits=2,
            ) == 0:
                payment.split_status = "balanced"

            elif float_compare(
                split_total,
                payment.total_amount,
                precision_digits=2,
            ) < 0:
                payment.split_status = "incomplete"

            else:
                payment.split_status = "excess"

    # =========================
    # PAYMENT STATE
    # =========================

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("refunded", "Refunded"),
        ],
        string="Status",
        required=True,
        default="draft",
        tracking=True,
    )
        # =========================
    # REFUND INFORMATION
    # =========================

    refunded_by = fields.Many2one(
        comodel_name="res.users",
        string="Refunded By",
        readonly=True,
        copy=False,
    )

    refunded_at = fields.Datetime(
        string="Refund Date",
        readonly=True,
        copy=False,
    )

    # =========================
    # CREATE PAYMENT REFERENCE
    # =========================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "restaurant.payment"
                    )
                    or "New"
                )

        return super().create(vals_list)

    # =========================
    # CHECK PAYMENT DATA
    # =========================

    def _check_payment_data(self):
        for payment in self:
            if not payment.order_id:
                raise UserError(
                    _("Please select an order.")
                )

            if payment.total_amount <= 0:
                raise UserError(
                    _("The total payment amount must be greater than zero.")
                )

            if payment.payment_type == "single":
                if not payment.method:
                    raise UserError(
                        _("Please select a payment method.")
                    )

            elif payment.payment_type == "split":
                if not payment.split_line_ids:
                    raise UserError(
                        _("Please add at least one split payment line.")
                    )

                for line in payment.split_line_ids:
                    if line.amount <= 0:
                        raise UserError(
                            _("Each split payment amount must be greater than zero.")
                        )

                if float_compare(
                    payment.split_total,
                    payment.total_amount,
                    precision_digits=2,
                ) != 0:
                    raise UserError(
                        _(
                            "The sum of split payment lines must equal "
                            "the total amount.\n"
                            "Total Amount: %(total).2f\n"
                            "Split Total: %(split).2f"
                        )
                        % {
                            "total": payment.total_amount,
                            "split": payment.split_total,
                        }
                    )

    # =========================
    # ACTIONS
    # =========================

    def action_submit(self):
        for payment in self:
            if payment.state != "draft":
                raise UserError(
                    _("Only draft payments can be submitted.")
                )

            payment._check_payment_data()
            payment.state = "pending"

    def action_post(self):
        """Mark the payment as paid."""
        for payment in self:
            if payment.state != "pending":
                raise UserError(
                    _("Only pending payments can be marked as paid.")
                )

            payment._check_payment_data()
            payment.state = "paid"

    def action_refund(self):
        for payment in self:
            if payment.state != "paid":
                raise UserError(
                    _("Only paid payments can be refunded.")
                )

            payment.write({
                "state": "refunded",
                "refunded_by": self.env.user.id,
                "refunded_at": fields.Datetime.now(),
            })

    def action_draft(self):
        for payment in self:
            if payment.state not in ("pending", "refunded"):
                raise UserError(
                    _("Only pending or refunded payments can return to draft.")
                )

            payment.state = "draft"

    # =========================
    # PREVENT DUPLICATE PAYMENT
    # =========================

    @api.constrains("order_id")
    def _check_one_payment_per_order(self):
        for payment in self:
            if payment.order_id:
                duplicate = self.search_count([
                    ("order_id", "=", payment.order_id.id),
                    ("id", "!=", payment.id),
                ])

                if duplicate:
                    raise ValidationError(
                        _(
                            "This order already has a payment record. "
                            "Use the existing payment record instead."
                        )
                    )