    # InvoiceAI

InvoiceAI is a Django-based invoice management application that lets users create, edit, save, and download professional invoices as PDFs. It also includes an AI-powered invoice assistant that understands natural-language descriptions and fills invoice fields automatically.

## Features

- 🔐 User authentication and login
- 🧾 Create and edit invoices
- 🎨 Four different invoice layouts/templates
- 🤖 AI Invoice Assistant
- 💬 Natural-language invoice input
- ❓ AI follow-up questions for missing information
- 📦 Dynamic invoice line items
- ➕ Add multiple products/services
- 🗑️ Delete or restore invoice items
- 💰 Automatic subtotal, discount, tax, and total calculation
- ⚡ Live total updates while editing
- 📄 Generate and download invoices as PDF
- 💾 Save invoices as drafts
- ✅ Finalized invoice status
- 📱 Responsive invoice editor
- 🖨️ Print-friendly invoice preview
- 🗃️ PostgreSQL support for production

## AI Invoice Assistant

The AI assistant allows users to describe an invoice naturally instead of manually entering every field.

For example:

> Create an invoice for ABC Technologies.  
> I provided 2 website development services at ₹25,000 each with 18% GST.  
> The invoice is due in 15 days.

The assistant extracts structured information such as:

- Seller details
- Customer details
- Invoice number
- Invoice date
- Due date
- Products/services
- Quantity
- Unit price
- Tax rate
- GST treatment
- Discount
- Notes

If required information is missing, the AI can ask follow-up questions before considering the invoice ready for review.

### AI Workflow

```text
User's natural-language prompt
            ↓
     Django AI endpoint
            ↓
       AI processing
            ↓
Structured invoice JSON
            ↓
Populate invoice form
            ↓
Live total calculation
            ↓
User reviews invoice
            ↓
Save / Download PDF
```

## Invoice Templates

InvoiceAI currently supports four distinct invoice designs.

### Template 1 — Professional

A clean and traditional invoice layout suitable for general business use.

### Template 2 — Luxury

A centered editorial design with elegant typography and gold-inspired accents.

### Template 3 — Modern Corporate

A structured corporate layout using a teal color system and strong section hierarchy.

### Template 4 — Creative Freelancer

A modern purple-themed layout with rounded cards and creative visual elements.

The invoice design can be changed directly from the invoice editor.

## Live Invoice Calculations

The invoice editor calculates totals dynamically in the browser.

```text
Subtotal
   ↓
Discount
   ↓
Tax calculation
   ↓
Final Total
```

For every line item:

```text
Line Amount = Quantity × Unit Price
```

Tax is then calculated from the applicable tax rate.

When the AI assistant fills quantity, unit price, tax rate, or discount, the frontend recalculates the totals immediately without requiring the user to manually edit another field.

The browser provides a live estimate while the Django backend remains authoritative when generating the final PDF.

## PDF Generation

Invoices can be converted into printable PDF documents.

The generated PDF includes:

- Seller information
- Customer information
- Invoice number
- Invoice and due dates
- Invoice items
- Quantity
- Unit price
- Tax
- Discount
- Final total
- Notes/payment terms
- Selected invoice design

PDF generation is handled server-side using Django and ReportLab.

## Technology Stack

### Backend

- Python
- Django
- Django Forms
- Django Formsets
- Django Authentication
- ReportLab

### Frontend

- HTML5
- CSS3
- JavaScript
- Django Templates
- Responsive CSS
- Google Fonts

### Database

Development:

- SQLite

Production:

- PostgreSQL

### AI

- OpenAI API
- Structured JSON invoice extraction
- AI follow-up questions

## Project Structure

A simplified project structure:

```text
thaagam_invoice/
│
├── manage.py
│
├── project/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── invoices/
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/
│   │   └── invoices/
│   │       ├── dashboard.html
│   │       ├── template_selection.html
│   │       └── create_invoice.html
│   └── ...
│
├── ai_agent/
│   ├── views.py
│   ├── templates/
│   │   └── ai_agent/
│   │       └── assistant.html
│   └── ...
│
├── requirements.txt
├── .env
└── README.md
```

> Folder names may differ depending on how the Django applications are organized in your project.

## Invoice Data Model

The invoice system stores information such as:

```text
Invoice
├── Owner
├── Invoice Number
├── Seller Name
├── Seller Address
├── Seller Mobile
├── Customer Name
├── Customer Address
├── Customer Mobile
├── Customer State
├── Invoice Date
├── Due Date
├── GST Type
├── Discount
├── Template
├── Status
├── Notes
└── Created At
```

Invoice items are handled through a Django formset and can contain:

```text
Invoice Item
├── Description
├── Quantity
├── Unit Price
└── Tax Rate
```

## Installation

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd thaagam_invoice
```

### 2. Create a Virtual Environment

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` has not been generated yet:

```bash
pip install django reportlab python-dotenv openai
```

For PostgreSQL:

```bash
pip install psycopg2-binary
```

## Environment Variables

Create a `.env` file in the project root.

Example:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True

OPENAI_API_KEY=your-openai-api-key

DATABASE_URL=your-database-url
```

For production, use secure secret values and set:

```env
DEBUG=False
```

Do not commit `.env` to Git.

Add it to `.gitignore`:

```gitignore
.env
venv/
__pycache__/
*.pyc
db.sqlite3
```

## Database Setup

Run migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

Create an administrator account:

```bash
python manage.py createsuperuser
```

## Run the Development Server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Typical User Flow

```text
Login
  ↓
Dashboard
  ↓
Create Invoice
  ↓
Select Invoice Template
  ↓
Enter details manually
        OR
Use AI Invoice Assistant
  ↓
AI fills invoice fields
  ↓
Review / edit invoice
  ↓
Live totals calculated
  ↓
Save Invoice
        OR
Save & Download PDF
```

## Django Formset Item Management

Invoice items use Django formsets, allowing users to dynamically add products or services.

The frontend updates:

```text
TOTAL_FORMS
```

when a new item is added.

Deleted items use Django's formset `DELETE` field, allowing existing database items to be marked for deletion while preserving correct formset behavior.

## Security

Recommended production practices:

- Keep `SECRET_KEY` in environment variables.
- Never commit API keys.
- Set `DEBUG=False` in production.
- Configure `ALLOWED_HOSTS`.
- Configure secure CSRF and session settings.
- Use HTTPS.
- Keep dependencies updated.
- Restrict database access.
- Protect invoice data by user ownership.
- Validate all invoice values server-side.
- Treat AI-generated data as untrusted input and validate it before saving.

## Production Deployment

The project can be deployed using services such as Render or another Django-compatible hosting provider.

Typical production setup:

```text
User
 ↓
HTTPS
 ↓
Web Server
 ↓
Django
 ↓
PostgreSQL
```

Static files should be collected before deployment:

```bash
python manage.py collectstatic --noinput
```

Run migrations during deployment:

```bash
python manage.py migrate
```

## Important AI Design Principle

The AI assistant should not directly save an invoice without user confirmation.

Recommended workflow:

```text
AI generates draft
      ↓
User reviews fields
      ↓
User corrects any mistakes
      ↓
User saves/finalizes invoice
      ↓
Server validates data
      ↓
PDF generated
```

This is important because AI-generated values such as prices, dates, quantities, tax rates, and customer information can contain mistakes.

## Future Improvements

Potential future enhancements:

- Multiple currencies
- Company logos
- Email invoice directly to customers
- Payment tracking
- Recurring invoices
- Invoice search and filtering
- Customer management
- Product/service catalog
- Automatic invoice numbering
- GST/IGST/CGST/SGST calculations
- Payment gateway integration
- Invoice analytics
- Cloud storage for PDFs
- Invoice sharing links
- Better AI conversation memory
- Voice-based invoice creation
- OCR for existing invoices

## Screenshots

Add project screenshots here:

```text
docs/
├── dashboard.png
├── invoice-editor.png
├── ai-assistant.png
├── invoice-template-1.png
├── invoice-template-2.png
├── invoice-template-3.png
├── invoice-template-4.png
└── invoice-pdf.png
```

Example Markdown:

```markdown
![Dashboard](docs/dashboard.png)
![Invoice Editor](docs/invoice-editor.png)
![AI Assistant](docs/ai-assistant.png)
```

## Development Notes

The invoice editor is intentionally designed to resemble the final printable document. Instead of using a separate traditional form layout, Django form fields are styled as editable elements directly inside the invoice canvas.

The AI assistant updates the same form fields used for manual editing, so users can combine AI-generated data with manual corrections.

The browser-side total calculation is for immediate user feedback. The backend should always recalculate and validate totals before producing the final invoice PDF.

## License

This project is currently intended for development, demonstration, and portfolio purposes.

Add your preferred license here if the project is released publicly.

---

## Author

**Jeyabalaganesh S**

Full-Stack Developer

- Portfolio: https://jeyabalaganesh.site/
- GitHub: https://github.com/jeyabalaganesh-s/
- LinkedIn: https://www.linkedin.com/in/jeyabalaganesh-s/

---

⭐ If you find this project useful, consider giving the repository a star.