
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Invoice

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from xml.sax.saxutils import escape

from .models import Invoice
from .forms import InvoiceForm, InvoiceItemFormSet


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Invoice

import re

from django.http import JsonResponse
from django.views.decorators.http import require_GET


from .models import Customer


from django.core.paginator import Paginator
# from django.contrib.auth.decorators import login_required
# from django.shortcuts import render
# from .models import Invoice





#import re

#from django.contrib import messages
#from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
#from django.shortcuts import render, redirect
#from django.utils import timezone

#from .models import Invoice, Customer
from .gst import get_seller_state, determine_gst_type



@login_required
def template_selection(request):
    return render(
        request,
        "invoices/template_selection.html",
    )



@login_required
def dashboard(request):
    invoice_queryset = Invoice.objects.filter(
        owner=request.user
    ).order_by("-created_at")

    # Pagination: 5 invoices per page
    paginator = Paginator(invoice_queryset, 5)
    page_obj = paginator.get_page(request.GET.get("page"))

    paid_invoices_count = invoice_queryset.filter(
        status="paid"
    ).count()

    pending_invoices_count = invoice_queryset.filter(
        status="pending"
    ).count()

    context = {
        "invoices": page_obj,
        "page_obj": page_obj,
        "total_invoices_count": paginator.count,
        "paid_invoices_count": paid_invoices_count,
        "pending_invoices_count": pending_invoices_count,
    }

    return render(request, "invoices/dashboard.html", context)






def normalize_mobile(value):
    digits = re.sub(r"\D", "", value or "")

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    return digits




@login_required
def create_invoice(request):
   
    allowed_templates = {
        "template_1",
        "template_2",
        "template_3",
        "template_4",
    }

    if request.method == "POST":
        selected_template = (
            request.POST.get("template")
            or request.session.get("selected_invoice_template")
            or "template_1"
        )
    else:
        selected_template = (
            request.GET.get("template")
            or request.session.get("selected_invoice_template")
            or "template_1"
        )

    if selected_template not in allowed_templates:
        selected_template = "template_1"

    request.session["selected_invoice_template"] = selected_template
    request.session.modified = True

    if request.method == "POST":
        invoice = Invoice(owner=request.user)

        form = InvoiceForm(request.POST, instance=invoice)
        item_formset = InvoiceItemFormSet(
            request.POST,
            instance=invoice,
            prefix="items",
        )

        if form.is_valid() and item_formset.is_valid():
            invoice = form.save(commit=False)
            invoice.owner = request.user

            # Never trust the template value supplied by the AI or form.
            invoice.template = selected_template

            try:
                mobile = normalize_mobile(
                    form.cleaned_data.get("customer_mobile", "")
                )

                if len(mobile) != 10:
                    form.add_error(
                        "customer_mobile",
                        "Enter a valid 10-digit Indian mobile number.",
                    )
                    raise ValueError("Invalid mobile number.")

                # Find an existing customer belonging to this user.
                customer = next(
                    (
                        item
                        for item in Customer.objects.filter(
                            owner=request.user
                        )
                        if normalize_mobile(item.mobile_number) == mobile
                    ),
                    None,
                )

                customer_created = False

                # Read customer details from the submitted form.
                # The AI agent should already have filled these fields.
                customer_name = (
                    form.cleaned_data.get("customer_name") or ""
                ).strip()

                customer_address = (
                    form.cleaned_data.get("customer_address") or ""
                ).strip()

                customer_state = (
                    form.cleaned_data.get("customer_state") or ""
                ).strip()

                with transaction.atomic():
                    # Automatically register a new customer when needed.
                    if customer is None:
                        missing = []

                        if not customer_name:
                            missing.append("customer name")

                        if not customer_address:
                            missing.append("customer address")

                        if not customer_state:
                            missing.append("customer state")

                        if missing:
                            form.add_error(
                                None,
                                "To register this new customer, provide: "
                                + ", ".join(missing)
                                + ". Please collect the state in the AI agent.",
                            )
                            raise ValueError(
                                "New customer details are incomplete."
                            )

                        customer = Customer.objects.create(
                            owner=request.user,
                            mobile_number=mobile,
                            name=customer_name,
                            address=customer_address,
                            state=customer_state,
                        )
                        customer_created = True

                    # Use the saved customer record.
                    invoice.customer_mobile = customer.mobile_number
                    invoice.customer_name = customer.name
                    invoice.customer_address = customer.address
                    invoice.customer_state = customer.state

                    # Calculate GST using the seller and customer states.
                    seller_state = get_seller_state()
                    invoice.seller_state = seller_state
                    invoice.gst_type = determine_gst_type(
                        seller_state,
                        customer.state,
                    )

                    if not invoice.gst_type:
                        raise ValueError(
                            "Valid seller and customer states are required."
                        )

                    invoice.full_clean()

                    # Diagnostic logs: verify the selected template.
                    print("SESSION TEMPLATE:", request.session.get(
                        "selected_invoice_template"
                    ))
                    print("SAVING TEMPLATE:", invoice.template)

                    invoice.save()

                    item_formset.instance = invoice
                    item_formset.save()

                request.session.pop("invoice_ai_draft", None)

                if customer_created:
                    messages.success(
                        request,
                        "Invoice saved and new customer registered successfully.",
                    )
                else:
                    messages.success(
                        request,
                        "Invoice saved successfully using the existing customer.",
                    )

                # Download the PDF for this newly saved invoice.
                
                action = request.POST.get("action", "save")

                if action == "download_pdf":
                    return redirect(
                        "invoice_pdf",
                        invoice_id=invoice.pk,
                    )

                # Save Invoice: save successfully and return to dashboard.
                return redirect("dashboard")


            except ValueError as exc:
                if not form.errors:
                    messages.error(request, str(exc))

            except IntegrityError:
                messages.error(
                    request,
                    "The invoice or customer could not be saved. "
                    "Check for duplicate mobile or invoice numbers.",
                )

            except Exception as exc:
                print(
                    f"Invoice save error: {type(exc).__name__}: {exc}"
                )
                messages.error(
                    request,
                    "The invoice could not be saved. "
                    "Please check the Django terminal for details.",
                )

        
        else:
            print("\n========== INVOICE VALIDATION DEBUG ==========")
            print("FORM VALID:", form.is_valid())
            print("FORM ERRORS:", form.errors.as_json())
            print("FORM DATA:", {
                key: request.POST.get(key)
                for key in [
                    "invoice_number",
                    "seller_name",
                    "seller_mobile",
                    "customer_name",
                    "customer_mobile",
                    "customer_state",
                    "invoice_date",
                    "gst_type",
                ]
            })

            print("FORMSET VALID:", item_formset.is_valid())
            print("FORMSET ERRORS:", item_formset.errors)
            print("FORMSET NON-FORM ERRORS:", item_formset.non_form_errors())
            print("POSTED ITEM DATA:", {
                key: value
                for key, value in request.POST.items()
                if key.startswith("items-")
            })
            print("==============================================\n")

            messages.error(
                request,
                "Please correct the errors shown in the form.",
            )


    else:
        invoice = Invoice(
            owner=request.user,
            template=selected_template,
        )

        form = InvoiceForm(
            instance=invoice,
            initial={
                "invoice_date": timezone.localdate(),
                "template": selected_template,
            },
        )

        # Explicitly initialize the template field.
        form.fields["template"].initial = selected_template

        item_formset = InvoiceItemFormSet(
            instance=invoice,
            prefix="items",
        )

    return render(
        request,
        "invoices/create_invoice.html",
        {
            "invoice_form": form,
            "item_formset": item_formset,
            "selected_template": selected_template,
            "editing_invoice": None,
            "invoice": invoice,
        },
    )





@login_required
def invoice_pdf(request, invoice_id):
    from decimal import Decimal

    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from xml.sax.saxutils import escape

    invoice = get_object_or_404(
        Invoice.objects.prefetch_related("items"),
        pk=invoice_id,
        owner=request.user,
    )

    # --------------------------------------------------
    # TEMPLATE CONFIGURATION
    # --------------------------------------------------
    designs = {
        "template_1": {
            "name": "Classic Professional",
            "primary": "#243B64",
            "accent": "#243B64",
            "light": "#EAF0F8",
            "border": "#D7DFEA",
            "font": "Helvetica",
        },
        "template_2": {
            "name": "Luxury",
            "primary": "#29251F",
            "accent": "#A68A48",
            "light": "#F7F2E6",
            "border": "#D9C99F",
            "font": "Times-Roman",
        },
        "template_3": {
            "name": "Modern Corporate",
            "primary": "#087E78",
            "accent": "#0D9488",
            "light": "#E5F6F3",
            "border": "#B9DFD8",
            "font": "Helvetica",
        },
        "template_4": {
            "name": "Creative Freelancer",
            "primary": "#6D28D9",
            "accent": "#A78BFA",
            "light": "#F1EAFF",
            "border": "#DDD0FA",
            "font": "Helvetica",
        },
    }

    template_key = invoice.template or "template_1"
    if template_key not in designs:
        template_key = "template_1"

    design = designs[template_key]
    primary = colors.HexColor(design["primary"])
    accent = colors.HexColor(design["accent"])
    light = colors.HexColor(design["light"])
    border = colors.HexColor(design["border"])
    font = design["font"]

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="invoice-{invoice.invoice_number}.pdf"'
    )

    pdf = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author=invoice.seller_name or "Invoice Generator",
    )

    styles = getSampleStyleSheet()
    story = []
    page_width = A4[0] - 36 * mm

    def safe(value):
        return escape(str(value or "-")).replace("\n", "<br/>")

    def money(value):
        return f"INR {value:,.2f}"

    body = ParagraphStyle(
        f"Body_{template_key}",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#374151"),
        spaceAfter=3,
    )

    small = ParagraphStyle(
        f"Small_{template_key}",
        parent=body,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    )

    section = ParagraphStyle(
        f"Section_{template_key}",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=primary,
        spaceBefore=7,
        spaceAfter=7,
    )

    title = ParagraphStyle(
        f"Title_{template_key}",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=33,
        textColor=primary,
        spaceAfter=5,
    )

    # --------------------------------------------------
    # TEMPLATE 1: CLASSIC PROFESSIONAL
    # --------------------------------------------------
    if template_key == "template_1":
        classic_seller = ParagraphStyle(
            "ClassicSeller",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=primary,
        )

        header = Table(
            [[
                [
                    Paragraph("INVOICE", title),
                    Paragraph(
                        f"<b>No.</b> {safe(invoice.invoice_number)}", body
                    ),
                    Paragraph(
                        f"<b>Date:</b> {safe(invoice.invoice_date)}", body
                    ),
                    Paragraph(
                        f"<b>Due:</b> {safe(invoice.due_date)}", small
                    ),
                ],
                [
                    Paragraph(safe(invoice.seller_name), classic_seller),
                    Paragraph(safe(invoice.seller_address), small),
                    Paragraph(
                        f"Mobile: {safe(getattr(invoice, 'seller_mobile', ''))}",
                        small,
                    ),
                ],
            ]],
            colWidths=[page_width * 0.52, page_width * 0.48],
        )

        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, -1), 2, primary),
        ]))

        story.append(header)
        story.append(Spacer(1, 9 * mm))

    # --------------------------------------------------
    # TEMPLATE 2: LUXURY
    # --------------------------------------------------
    elif template_key == "template_2":
        centered_title = ParagraphStyle(
            "LuxuryTitle",
            parent=title,
            fontName="Times-Roman",
            fontSize=31,
            leading=37,
            alignment=TA_CENTER,
            textColor=accent,
            spaceAfter=10,
        )

        centered = ParagraphStyle(
            "LuxuryCentered",
            parent=body,
            alignment=TA_CENTER,
        )

        luxury_seller = ParagraphStyle(
            "LuxurySeller",
            parent=centered,
            fontName="Times-Roman",
            fontSize=14,
            textColor=primary,
        )

        story.append(Paragraph("INVOICE", centered_title))
        story.append(Paragraph(
            f"<b>{safe(invoice.seller_name)}</b>", luxury_seller
        ))
        story.append(Paragraph(safe(invoice.seller_address), centered))
        story.append(Paragraph(
            f"Mobile: {safe(getattr(invoice, 'seller_mobile', ''))}",
            centered,
        ))
        story.append(Spacer(1, 5 * mm))

        divider = Table(
            [[""]],
            colWidths=[page_width],
            rowHeights=[2],
        )
        divider.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), accent),
        ]))
        story.append(divider)
        story.append(Spacer(1, 7 * mm))

        metadata = Table(
            [[
                Paragraph(
                    f"<b>INVOICE NUMBER</b><br/>"
                    f"{safe(invoice.invoice_number)}",
                    body,
                ),
                Paragraph(
                    f"<b>ISSUED</b><br/>{safe(invoice.invoice_date)}",
                    body,
                ),
                Paragraph(
                    f"<b>DUE DATE</b><br/>{safe(invoice.due_date)}",
                    body,
                ),
            ]],
            colWidths=[page_width / 3] * 3,
        )

        metadata.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), light),
            ("BOX", (0, 0), (-1, -1), 0.8, border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

        story.append(metadata)
        story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------
    # TEMPLATE 3: MODERN CORPORATE
    # --------------------------------------------------
    elif template_key == "template_3":
        seller_style = ParagraphStyle(
            "CorporateSeller",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.white,
        )

        address_style = ParagraphStyle(
            "CorporateAddress",
            parent=small,
            textColor=colors.white,
        )

        invoice_title = ParagraphStyle(
            "CorporateInvoiceTitle",
            parent=title,
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=colors.white,
            alignment=TA_RIGHT,
        )

        meta_style = ParagraphStyle(
            "CorporateInvoiceMeta",
            parent=small,
            textColor=colors.HexColor("#C8F4ED"),
            alignment=TA_RIGHT,
        )

        corporate_header = Table(
            [[
                [
                    Paragraph("FROM", meta_style),
                    Paragraph(safe(invoice.seller_name), seller_style),
                    Paragraph(safe(invoice.seller_address), address_style),
                    Paragraph(
                        f"Mobile: {safe(getattr(invoice, 'seller_mobile', ''))}",
                        address_style,
                    ),
                ],
                [
                    Paragraph("INVOICE", invoice_title),
                    Paragraph(
                        f"<b>{safe(invoice.invoice_number)}</b>"
                        f"<br/>DATE: {safe(invoice.invoice_date)}"
                        f"<br/>DUE: {safe(invoice.due_date)}",
                        meta_style,
                    ),
                ],
            ]],
            colWidths=[page_width * 0.55, page_width * 0.45],
        )

        corporate_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), primary),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ]))

        story.append(corporate_header)
        story.append(Spacer(1, 7 * mm))

    # --------------------------------------------------
    # TEMPLATE 4: CREATIVE FREELANCER
    # --------------------------------------------------
    else:
        creative_title = ParagraphStyle(
            "CreativeTitle",
            parent=title,
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.white,
        )

        creative_seller = ParagraphStyle(
            "CreativeSeller",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.white,
        )

        creative_info = ParagraphStyle(
            "CreativeInfo",
            parent=small,
            textColor=colors.white,
        )

        creative_number = ParagraphStyle(
            "CreativeNumber",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=colors.white,
            alignment=TA_RIGHT,
        )

        creative_header = Table(
            [[
                [
                    Paragraph("FROM", creative_info),
                    Paragraph(safe(invoice.seller_name), creative_seller),
                    Paragraph(safe(invoice.seller_address), creative_info),
                    Paragraph(
                        f"Mobile: {safe(getattr(invoice, 'seller_mobile', ''))}",
                        creative_info,
                    ),
                ],
                [
                    Paragraph("INVOICE", creative_title),
                    Paragraph("INVOICE NUMBER", creative_info),
                    Paragraph(safe(invoice.invoice_number), creative_number),
                    Spacer(1, 4 * mm),
                    Paragraph(
                        f"<b>DATE:</b> {safe(invoice.invoice_date)}"
                        f"<br/><b>DUE:</b> {safe(invoice.due_date)}",
                        creative_info,
                    ),
                ],
            ]],
            colWidths=[page_width * 0.53, page_width * 0.47],
        )

        creative_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), primary),
            ("BACKGROUND", (1, 0), (1, 0), accent),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 17),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 17),
        ]))

        story.append(creative_header)
        story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------
    # CUSTOMER DETAILS
    # --------------------------------------------------
    story.append(Paragraph(
        "CLIENT DETAILS" if template_key == "template_4" else "BILL TO",
        section,
    ))

    customer_name_style = ParagraphStyle(
        f"CustomerName_{template_key}",
        parent=body,
        fontSize=11,
        textColor=primary,
    )

    customer_details = [
        Paragraph(
            f"<b>{safe(invoice.customer_name)}</b>",
            customer_name_style,
        ),
        Paragraph(safe(invoice.customer_address), small),
    ]

    customer_mobile = getattr(invoice, "customer_mobile", "")
    if customer_mobile:
        customer_details.append(
            Paragraph(f"Mobile: {safe(customer_mobile)}", small)
        )

    customer_state = getattr(invoice, "customer_state", "")
    if customer_state:
        customer_details.append(
            Paragraph(f"State: {safe(customer_state)}", small)
        )

    if template_key in ("template_2", "template_3", "template_4"):
        customer_box = Table(
            [[customer_details]],
            colWidths=[page_width],
        )

        if template_key == "template_2":
            customer_box_style = [
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("BACKGROUND", (0, 0), (-1, -1), light),
            ]
        elif template_key == "template_3":
            customer_box_style = [
                ("BACKGROUND", (0, 0), (-1, -1), light),
                ("LINEBEFORE", (0, 0), (0, -1), 3, primary),
            ]
        else:
            customer_box_style = [
                ("BOX", (0, 0), (-1, -1), 1, border),
                ("BACKGROUND", (0, 0), (-1, -1), light),
            ]

        customer_box.setStyle(TableStyle(
            customer_box_style + [
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        ))
        story.append(customer_box)
    else:
        story.extend(customer_details)

    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph("ITEMS & SERVICES", section))

    # --------------------------------------------------
    # ITEM CALCULATIONS AND TABLE
    # --------------------------------------------------
    subtotal = Decimal("0")
    total_tax = Decimal("0")
    cgst_total = Decimal("0")
    sgst_total = Decimal("0")
    igst_total = Decimal("0")

    rows = [[
        Paragraph("<b>Description</b>", body),
        Paragraph("<b>Qty</b>", body),
        Paragraph("<b>Unit Price</b>", body),
        Paragraph("<b>Tax</b>", body),
        Paragraph("<b>Line Total</b>", body),
    ]]

    for item in invoice.items.all():
        quantity = Decimal(str(item.quantity or 0))
        unit_price = Decimal(str(item.unit_price or 0))
        tax_rate = Decimal(str(item.tax_rate or 0))

        amount = quantity * unit_price
        tax = amount * tax_rate / Decimal("100")

        subtotal += amount
        total_tax += tax

        if invoice.gst_type == "inter_state":
            igst_total += tax
        else:
            cgst_total += tax / Decimal("2")
            sgst_total += tax / Decimal("2")

        rows.append([
            Paragraph(safe(item.description), body),
            str(item.quantity),
            money(unit_price),
            f"{tax_rate:.2f}%",
            money(amount + tax),
        ])

    if len(rows) == 1:
        rows.append([
            Paragraph("No invoice items", body),
            "-",
            money(Decimal("0")),
            "0%",
            money(Decimal("0")),
        ])

    items_table = Table(
        rows,
        colWidths=[
            page_width * 0.38,
            page_width * 0.10,
            page_width * 0.19,
            page_width * 0.11,
            page_width * 0.22,
        ],
        repeatRows=1,
    )

    if template_key == "template_1":
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, light]),
        ]
    elif template_key == "template_2":
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), primary),
            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.HexColor("#F7EDDA")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, accent),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, border),
        ]
    elif template_key == "template_3":
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), primary),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, light]),
        ]
    else:
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), light),
            ("TEXTCOLOR", (0, 0), (-1, 0), primary),
            ("LINEBELOW", (0, 0), (-1, 0), 2, accent),
            ("LINEBELOW", (0, 1), (-1, -1), 0.6, border),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, light]),
        ]

    items_table.setStyle(TableStyle(
        table_style + [
            ("TEXTCOLOR", (0, 1), (-1, -1),
             colors.HexColor("#374151")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]
    ))

    story.append(items_table)
    story.append(Spacer(1, 8 * mm))

    # --------------------------------------------------
    # TOTALS: SUBTOTAL, DISCOUNT AND GST
    # --------------------------------------------------
    discount = Decimal(str(invoice.discount or 0))
    taxable_amount = max(Decimal("0"), subtotal - discount)

    if subtotal > 0 and discount > 0:
        ratio = taxable_amount / subtotal
        total_tax *= ratio
        cgst_total *= ratio
        sgst_total *= ratio
        igst_total *= ratio

    grand_total = taxable_amount + total_tax

    totals_rows = [
        ["Subtotal", money(subtotal)],
        ["Discount", money(discount)],
        ["Taxable amount", money(taxable_amount)],
    ]

    if invoice.gst_type == "inter_state":
        totals_rows.append(["IGST", money(igst_total)])
    else:
        totals_rows.extend([
            ["CGST", money(cgst_total)],
            ["SGST", money(sgst_total)],
        ])

    totals_rows.append(["GRAND TOTAL", money(grand_total)])

    
    totals_table = Table(
        [[
            Paragraph(
                f"<b>{safe(label)}</b>" if label == "GRAND TOTAL"
                else safe(label),
                body,
            ),
            Paragraph(
                f"<b>{safe(value)}</b>" if label == "GRAND TOTAL"
                else safe(value),
                body,
            ),
        ] for label, value in totals_rows],
        colWidths=[
            page_width * 0.275,
            page_width * 0.225,
        ],
        hAlign="RIGHT",
    )


    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), light),
        ("TEXTCOLOR", (0, -1), (-1, -1), primary),
        ("LINEABOVE", (0, -1), (-1, -1), 1.5, accent),
        ("BOX", (0, -1), (-1, -1), 0.8, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(totals_table)

    # --------------------------------------------------
    # DUE DATE, NOTES AND FOOTER
    # --------------------------------------------------
    if invoice.due_date:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(
            f"<b>Payment due date:</b> {safe(invoice.due_date)}",
            small,
        ))

    # UPDATED: Notes/payment terms use half the available page width.
    if invoice.notes:
        story.append(Spacer(1, 5 * mm))

        notes_content = [
            Paragraph("NOTES / PAYMENT TERMS", section),
            Paragraph(safe(invoice.notes), body),
        ]

        notes_table = Table(
            [[notes_content, ""]],
            colWidths=[
                page_width * 0.5,
                page_width * 0.5,
            ],
            hAlign="LEFT",
        )

        notes_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

        story.append(notes_table)

    story.append(Spacer(1, 12 * mm))

    footer_messages = {
        "template_1": "Thank you for your business.",
        "template_2": "Thank you for your trust and continued partnership.",
        "template_3": "We appreciate the opportunity to work with you.",
        "template_4": "Thanks for making great things happen together.",
    }

    footer_style = ParagraphStyle(
        f"Footer_{template_key}",
        parent=small,
        alignment=TA_CENTER,
        textColor=accent,
        fontName=font,
        fontSize=9,
    )

    footer = Table(
        [[Paragraph(
            safe(footer_messages[template_key]),
            footer_style,
        )]],
        colWidths=[page_width],
    )

    footer.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 1, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1),
         light if template_key in ("template_3", "template_4")
         else colors.white),
    ]))

    story.append(footer)

    pdf.build(story)
    return response 


def normalize_mobile(value):
    # Keep digits only; remove India's country code for 10-digit matching.
    digits = re.sub(r"\D", "", value or "")

    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    return digits


@login_required
@require_GET
def find_customer_by_mobile(request):
    mobile = normalize_mobile(request.GET.get("mobile", ""))

    if len(mobile) != 10:
        return JsonResponse(
            {"error": "Enter a valid 10-digit mobile number."},
            status=400,
        )

    customers = Customer.objects.filter(owner=request.user)

    # Match against normalized values to support common phone formats.
    customer = next(
        (
            item
            for item in customers
            if normalize_mobile(item.mobile_number) == mobile
        ),
        None,
    )

    if customer is None:
        return JsonResponse({
            "found": False,
            "message": "Customer not found. Enter their details to save them.",
        })

    return JsonResponse({
        "found": True,
        "customer": {
            "name": customer.name,
            "mobile_number": customer.mobile_number,
            "address": customer.address,
            "state": customer.state,
        },
    })


from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction



@login_required
def edit_invoice(request, invoice_id):
    allowed_templates = {
        "template_1",
        "template_2",
        "template_3",
        "template_4",
    }

    # Only allow the logged-in user to edit their own invoice.
    invoice = get_object_or_404(
        Invoice.objects.prefetch_related("items"),
        pk=invoice_id,
        owner=request.user,
    )

    selected_template = (
        request.POST.get("template")
        or invoice.template
        or "template_1"
    )

    if selected_template not in allowed_templates:
        selected_template = invoice.template or "template_1"

    if request.method == "POST":
        form = InvoiceForm(
            request.POST,
            instance=invoice,
        )

        item_formset = InvoiceItemFormSet(
            request.POST,
            instance=invoice,
            prefix="items",
        )

        print("FORMSET CAN DELETE:", item_formset.can_delete)
        print("FORM VALID:", form.is_valid())
        print("FORM ERRORS:", form.errors)
        print("FORMSET VALID:", item_formset.is_valid())
        print("FORMSET ERRORS:", item_formset.errors)

        if form.is_valid() and item_formset.is_valid():
            updated_invoice = form.save(commit=False)
            updated_invoice.owner = request.user
            updated_invoice.template = selected_template

            try:
                # Validate the submitted customer mobile number.
                mobile = normalize_mobile(
                    form.cleaned_data.get("customer_mobile", "")
                )

                if len(mobile) != 10:
                    form.add_error(
                        "customer_mobile",
                        "Enter a valid 10-digit Indian mobile number.",
                    )
                    raise ValueError(
                        "Invalid customer mobile number."
                    )

                # Find the customer's saved record for this user.
                customer = next(
                    (
                        item
                        for item in Customer.objects.filter(
                            owner=request.user
                        )
                        if normalize_mobile(item.mobile_number) == mobile
                    ),
                    None,
                )

                if customer is None:
                    form.add_error(
                        "customer_mobile",
                        "Customer not found. Save the customer details first.",
                    )
                    raise ValueError("Customer not found.")

                # Read the edited values from the submitted invoice form.
                customer_name = (
                    form.cleaned_data.get("customer_name")
                    or customer.name
                ).strip()

                customer_address = (
                    form.cleaned_data.get("customer_address")
                    if form.cleaned_data.get("customer_address") is not None
                    else customer.address
                ).strip()

                customer_state = (
                    form.cleaned_data.get("customer_state")
                    or customer.state
                ).strip()

                # Recalculate GST using the edited customer state.
                seller_state = get_seller_state()
                gst_type = determine_gst_type(
                    seller_state,
                    customer_state,
                )

                if not gst_type:
                    raise ValueError(
                        "Valid seller and customer states are required."
                    )

                # Update both database records atomically.
                with transaction.atomic():
                    # 1. Update the saved Customer record.
                    customer.name = customer_name
                    customer.address = customer_address
                    customer.state = customer_state

                    customer.save(
                        update_fields=[
                            "name",
                            "address",
                            "state",
                        ]
                    )

                    # 2. Update the current Invoice record.
                    updated_invoice.customer_mobile = (
                        customer.mobile_number
                    )
                    updated_invoice.customer_name = customer.name
                    updated_invoice.customer_address = customer.address
                    updated_invoice.customer_state = customer.state
                    updated_invoice.seller_state = seller_state
                    updated_invoice.gst_type = gst_type

                    updated_invoice.full_clean()
                    updated_invoice.save()

                    # Save existing, added, and deleted invoice items.
                    item_formset.instance = updated_invoice
                    item_formset.save()

                messages.success(
                    request,
                    "Invoice and customer details updated successfully.",
                )

                # Download the PDF only when requested.
                action = request.POST.get("action", "save")

                if action == "download_pdf":
                    return redirect(
                        "invoice_pdf",
                        invoice_id=updated_invoice.pk,
                    )

                # Otherwise, return to the dashboard.
                return redirect("dashboard")

            except ValueError as exc:
                if not form.errors:
                    messages.error(request, str(exc))

            except ValidationError as exc:
                messages.error(
                    request,
                    "Please correct the invoice details: "
                    + "; ".join(exc.messages),
                )

            except IntegrityError:
                messages.error(
                    request,
                    "The invoice could not be updated. "
                    "Check for duplicate invoice numbers.",
                )

            except Exception as exc:
                # Keep detailed errors in the development terminal.
                print(
                    f"Invoice update error: {type(exc).__name__}: {exc}"
                )
                messages.error(
                    request,
                    "The invoice could not be updated. "
                    "Please check the Django terminal for details.",
                )

        else:
            print(
                "POSTED DELETE FIELDS:",
                {
                    key: value
                    for key, value in request.POST.items()
                    if key.endswith("-DELETE")
                },
            )
            print("ITEM FORMSET ERRORS:", item_formset.errors)

            messages.error(
                request,
                "Please correct the errors shown in the form.",
            )

    else:
        # Load the existing invoice and its saved line items.
        form = InvoiceForm(instance=invoice)

        item_formset = InvoiceItemFormSet(
            instance=invoice,
            prefix="items",
        )

    return render(
        request,
        "invoices/create_invoice.html",
        {
            "invoice": invoice,
            "invoice_form": form,
            "item_formset": item_formset,
            "selected_template": selected_template,
            "editing_invoice": True,
        },
    )
@login_required
@require_POST
def update_invoice_status(request, invoice_id):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        owner=request.user,
    )

    new_status = request.POST.get("status", "")

    valid_statuses = dict(Invoice.STATUS_CHOICES)

    if new_status not in valid_statuses:
        messages.error(request, "Invalid invoice status.")
        return redirect("dashboard")

    invoice.status = new_status
    invoice.save(update_fields=["status"])

    messages.success(
        request,
        f"Invoice {invoice.invoice_number} status updated "
        f"to {invoice.get_status_display()}.",
    )

    return redirect("dashboard")