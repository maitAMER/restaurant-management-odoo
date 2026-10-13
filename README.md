# Restaurant & Delivery Management

An Odoo 17 custom addon for restaurant menu administration, orders, table reservations, customer records, payments, delivery assignment, and equipment maintenance.

| Property | Value |
| --- | --- |
| Technical module name | `restaurant_management` |
| Addon directory | `my_adds/restaurant_management/restaurant_management` |
| Odoo dependencies | `base`, `mail`, `product`, `crm`, `website` |
| Python dependency | `xlsxwriter` for Excel exports |

## Implemented Scope

### Models and relationships

- `restaurant.menu.category` has menu items; `restaurant.menu.item` stores menu section, price, cost, allergens, ingredients, preparation time, availability, and daily-special data.
- `restaurant.customer` stores individual or corporate customer details, optional user linkage, favorite menu items, loyalty balance, and loyalty transactions.
- `restaurant.order` links to a required Odoo contact (`res.partner`) and optionally to a restaurant customer. It has `restaurant.order.line` items, an optional table and delivery driver, amounts, and payment relations.
- `restaurant.table` tracks capacity, location, reservations, and orders. Availability is computed from active reservations and orders; a scheduled job refreshes the status.
- `restaurant.reservation` links a restaurant customer and table and tracks duration, guests, and reservation status.
- `restaurant.payment` belongs to an order and has a restaurant-customer related field, payment method/type, status, tips, and optional `restaurant.payment.split.line` records.
- `restaurant.equipment` has `restaurant.equipment.maintenance` tickets, including equipment type, urgency, assignment, status, schedule, and repair cost.
- `crm.lead` is extended with restaurant customer/category/source/order fields and an action intended to convert leads to orders.

### Back-office workflows

- Orders use `draft`, `confirmed`, `preparing`, `ready`, `completed`, `cancelled`, and `no_show` states. The form, kitchen board, and delivery queue expose state actions; model validations restrict edits and check order type, table availability, and order lines.
- Reservations use `draft`, `confirmed`, `seated`, `no_show`, and `cancelled` states. The model checks table capacity and overlapping reservations and includes reminder and no-show scheduled jobs.
- Payments use `draft`, `pending`, `paid`, and `refunded` states. Single payments use one method; split payments use separate method/amount lines and validate the split total when submitted or posted.
- Maintenance tickets use `draft`, `submitted`, `assigned`, `in_progress`, `done`, and `cancelled` states. An assignment wizard assigns technicians; active maintenance can update equipment status.
- Sequences are declared for customers, reservations, payments, orders, tables, and maintenance tickets.

### Website and customer portal

The website controller and QWeb templates provide a public menu and item detail page, table reservation pages, a catering inquiry form, and a website order submission path that creates draft orders. The public menu/detail routes restrict displayed items to available items. Authenticated users can open `/my/orders` to see orders associated with their restaurant-customer record and the loyalty balance.

The reservation availability check is a public JSON route at `/restaurant/reserve/check`. Website pages also include `/menu`, `/menu/<item_id>/<slug>`, `/restaurant/reserve`, `/restaurant/catering`, and their form submission routes. These are Odoo controller routes, not a separately versioned public web API.

### Reports and exports

- A QWeb PDF order receipt is registered for `restaurant.order`.
- The sales report wizard has preview and Excel export actions for daily sales, costs, profit/loss, tips, average order, and top items.
- An authenticated controller route is present for exporting an individual order receipt as Excel: `/restaurant/order/<order_id>/receipt/excel`.

These report implementations are present in source but have known field/state mismatches listed below; verify them before relying on exported results.

## API and External Integrations

`controllers/api.py` contains two JSON routes: `/api/restaurant/login` and `/api/restaurant/orders/create`. The login route looks up `restaurant.api_token`, but this addon does not define that model. The order route creates an order from a limited payload and does not create order lines. Treat both routes as incomplete and do not use them as a production integration contract.

No AI assistant implementation or n8n workflow/webhook integration was found in the addon source. A comment mentions a possible AI wizard, but no corresponding implementation is loaded.

## Security

The access-control CSV grants `base.group_user` read, write, create, and delete access to the listed restaurant models. Loyalty transactions specifically allow read, create, and delete but not write for this group. Public website controller methods use elevated access for some menu and reservation operations; review their inputs and record access before production deployment.

Several views and model fields reference `restaurant_management.group_shift_manager`; the controller imports also previously referenced restaurant-specific user groups in demo data. No definitions for these custom groups are included in the addon files currently listed by the manifest. Define and load the groups or remove/replace the references before relying on role-specific access. No record-rule file is declared in the current manifest.

## Installation

Run these commands from the repository workspace root (`Odoo_17/`). Use an existing Odoo 17 environment with the dependencies in `odoo/requirements.txt` installed.

1. Install the addon's declared Python dependency in the Odoo environment:

	```bash
	./venv_17/bin/python -m pip install xlsxwriter
	```

2. Ensure the configured `addons_path` includes the directory containing the addon folder:

	```text
	/path/to/Odoo_17/my_adds/restaurant_management
	```

	The workspace `odoo.conf` already includes this path.

3. Install the module into a database:

	```bash
	./venv_17/bin/python odoo/odoo-bin -c odoo.conf -d <database_name> -i restaurant_management --stop-after-init
	```

4. After changing the addon, upgrade it with `-u` instead of `-i`:

	```bash
	./venv_17/bin/python odoo/odoo-bin -c odoo.conf -d <database_name> -u restaurant_management --stop-after-init
	```

The file `data/restaurant_data.xml` exists but is not currently included in the manifest's `data` list, so its sample records are not loaded by these commands. The manifest does load `data/ir_sequence_data.xml` and the listed views, security CSV, wizard, and report files.

## Project Structure

```text
Odoo_17/
├── odoo/                               # Odoo 17 server source
├── my_adds/
│   ├── Real_state_project/             # Separate custom addon area
│   └── restaurant_management/
│       └── restaurant_management/      # This addon
│           ├── controllers/            # Website, JSON API, Excel receipt routes
│           ├── data/                   # Sequences and currently unlisted sample data
│           ├── models/                 # Restaurant business models
│           ├── report/                 # PDF report registration and sales report model
│           ├── security/               # Model access CSV
│           ├── views/                  # Back-office, website, and portal XML
│           └── wizard/                 # Sales report and maintenance assignment wizards
├── odoo.conf                           # Local Odoo configuration
└── venv_17/                            # Local Python environment (not source-controlled deployment config)
```

## Known Gaps and Verification

- The sales report currently filters orders by state `delivered`, which is not a state in `restaurant.order`; its cost and top-item calculations also reference line fields such as `order_line_ids` and `product_id` that do not match the current order-line model (`line_ids`, `menu_item_id`, `price_subtotal`).
- The sales report model is defined in both `report/restaurant_report.py` and `wizard/sales_report_wizard.py`; consolidate or verify which implementation Odoo loads before relying on it.
- The PDF receipt template and Excel receipt controller also contain old order-line field names and need alignment with the current models before their output can be considered verified.
- The website reservation submit controller passes `restaurant_customer_id` to `restaurant.reservation`, whose field is named `customer_id`. For public bookings it may also create an order without the required `res.partner` customer. Exercise and repair this flow before launch.
- CRM lead conversion currently passes a `restaurant.customer` ID to the order's `res.partner` customer field and creates no order lines; the conversion flow requires correction and testing.
- The custom group XML IDs used by views/fields are not defined in the current addon data. Verify module installation and access behavior after resolving them.
- The JSON API needs a token model/authentication design and complete order-line validation. No AI assistant, n8n integration, or automated tests are present in the addon files reviewed.
- The website menu controller treats `category_id` as an integer menu-section value, while menu sections are string selections and menu categories are separate records. Category filtering needs verification.



The n8n workflow JSON export used for the Telegram bot integration is located in n8n_workflows/restaurant_bot_workflow.json.

Project Team:
