from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from sales.models import Sale, SaleItem
from products.models import Product
from django.db.models import Sum, Count, F, Q
from collections import defaultdict
from io import BytesIO
import json

# Configurar matplotlib antes de importar
import matplotlib  # type: ignore
matplotlib.use('Agg')  # Backend não-interativo
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.patches as mpatches  # type: ignore
from matplotlib.backends.backend_agg import FigureCanvasAgg  # type: ignore

# Imports do reportlab
from reportlab.lib.pagesizes import letter, A4  # type: ignore  # noqa: F401
from reportlab.lib import colors  # type: ignore
from reportlab.lib.units import inch  # type: ignore
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image  # type: ignore
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
from reportlab.lib.enums import TA_CENTER, TA_LEFT  # type: ignore


def _get_report_data(start_date, end_date):
    """Função auxiliar para calcular dados do relatório"""
    # Filtrar vendas finalizadas no período
    sales = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Preparar dados para o relatório
    # 1. Vendas por mês
    sales_by_month = defaultdict(Decimal)
    for sale in sales:
        month_key = sale.created_at.strftime('%Y-%m')
        sales_by_month[month_key] += sale.total
    
    # Ordenar por mês
    months_data = sorted(sales_by_month.items())
    months_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    months_labels = [months_pt[int(m.split('-')[1]) - 1] for m, _ in months_data]
    months_values = [float(v) for _, v in months_data]
    
    # 2. Participação por produto
    product_sales = defaultdict(lambda: {'quantity': 0, 'total': Decimal('0.00')})
    for sale in sales:
        for item in sale.items.all():
            product_sales[item.product.name]['quantity'] += item.quantity
            product_sales[item.product.name]['total'] += item.price * item.quantity
    
    # Ordenar produtos por total vendido
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['total'], reverse=True)
    
    # Pegar top 4 produtos e agrupar o resto em "Outros"
    top_products = sorted_products[:4]
    others_total = sum(p[1]['total'] for p in sorted_products[4:])
    others_quantity = sum(p[1]['quantity'] for p in sorted_products[4:])
    
    if others_total > 0:
        top_products.append(('Outros', {'quantity': others_quantity, 'total': others_total}))
    
    # Calcular percentuais
    total_sales = sum(p[1]['total'] for p in product_sales.values())
    product_percentages = []
    for name, data in top_products:
        percentage = (data['total'] / total_sales * 100) if total_sales > 0 else 0
        product_percentages.append({
            'name': name,
            'percentage': percentage,
            'total': float(data['total']),
            'quantity': data['quantity']
        })
    
    # 3. Estatísticas gerais
    total_vendas = sales.aggregate(total=Sum(F('items__price') * F('items__quantity')))['total'] or Decimal('0.00')
    total_produtos_vendidos = SaleItem.objects.filter(
        sale__in=sales
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Produto mais vendido
    most_sold_product = None
    if sorted_products:
        most_sold_product = {
            'name': sorted_products[0][0],
            'quantity': sorted_products[0][1]['quantity']
        }
    
    # Produto menos vendido (dos que foram vendidos)
    least_sold_product = None
    if sorted_products and len(sorted_products) > 1:
        least_sold_product = {
            'name': sorted_products[-1][0],
            'quantity': sorted_products[-1][1]['quantity']
        }
    
    # Produtos em falta (quantidade = 0)
    out_of_stock = Product.objects.filter(quantity=0).count()
    
    return {
        'months_labels': months_labels,
        'months_values': months_values,
        'product_percentages': product_percentages,
        'total_vendas': float(total_vendas),
        'total_produtos_vendidos': total_produtos_vendidos,
        'out_of_stock': out_of_stock,
        'most_sold_product': most_sold_product,
        'least_sold_product': least_sold_product,
        'start_date': start_date.strftime('%d/%m/%Y'),
        'end_date': end_date.strftime('%d/%m/%Y'),
        'has_data': sales.exists()
    }


@login_required
def dashboard_view(request):
    """View principal do dashboard"""
    from clients.models import Client
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Vendas do dia (finalizadas)
    sales_today = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=today_start,
        created_at__lte=today_end
    )
    total_sales_today = sales_today.aggregate(
        total=Sum(F('items__price') * F('items__quantity'))
    )['total'] or Decimal('0.00')
    count_sales_today = sales_today.count()
    
    # Vendas do mês (finalizadas)
    sales_month = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=month_start,
        created_at__lte=now
    )
    total_sales_month = sales_month.aggregate(
        total=Sum(F('items__price') * F('items__quantity'))
    )['total'] or Decimal('0.00')
    count_sales_month = sales_month.count()
    
    # Vendas abertas (pendentes)
    open_sales = Sale.objects.filter(status=Sale.STATUS_OPEN)
    count_open_sales = open_sales.count()
    total_open_sales = open_sales.aggregate(
        total=Sum(F('items__price') * F('items__quantity'))
    )['total'] or Decimal('0.00')
    
    # Total de dívidas (clientes com fiado)
    total_debts = Client.objects.aggregate(
        total=Sum('client_debts')
    )['total'] or Decimal('0.00')
    clients_with_debts = Client.objects.filter(client_debts__gt=0).count()
    
    # Produtos em falta
    out_of_stock_count = Product.objects.filter(quantity=0, is_active=True).count()
    low_stock_count = Product.objects.filter(
        quantity__gt=0, 
        quantity__lte=F('low_quantity'),
        is_active=True
    ).count()
    
    # Total de produtos ativos
    total_products = Product.objects.filter(is_active=True).count()
    
    # Total de clientes
    total_clients = Client.objects.count()
    
    # Vendas recentes (últimas 5 finalizadas)
    recent_sales = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED
    ).order_by('-created_at')[:5]
    
    # Top 5 produtos mais vendidos (últimos 30 dias)
    thirty_days_ago = now - timedelta(days=30)
    recent_sales_30d = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=thirty_days_ago
    )
    
    product_sales_30d = defaultdict(lambda: {'quantity': 0, 'total': Decimal('0.00')})
    for sale in recent_sales_30d:
        for item in sale.items.all():
            product_sales_30d[item.product.name]['quantity'] += item.quantity
            product_sales_30d[item.product.name]['total'] += item.price * item.quantity
    
    top_products = sorted(
        product_sales_30d.items(), 
        key=lambda x: x[1]['quantity'], 
        reverse=True
    )[:5]
    
    # Vendas por dia da semana (últimos 7 dias)
    sales_by_day_labels = []
    sales_by_day_values = []
    for i in range(6, -1, -1):  # De 6 dias atrás até hoje (ordem reversa)
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        day_sales = Sale.objects.filter(
            status=Sale.STATUS_FINALIZED,
            created_at__gte=day_start,
            created_at__lte=day_end
        )
        day_total = day_sales.aggregate(
            total=Sum(F('items__price') * F('items__quantity'))
        )['total'] or Decimal('0.00')
        sales_by_day_labels.append(day.strftime('%d/%m'))
        sales_by_day_values.append(float(day_total))
    
    context = {
        'section_name': 'Dashboard',
        'total_sales_today': float(total_sales_today),
        'count_sales_today': count_sales_today,
        'total_sales_month': float(total_sales_month),
        'count_sales_month': count_sales_month,
        'count_open_sales': count_open_sales,
        'total_open_sales': float(total_open_sales),
        'total_debts': float(total_debts),
        'clients_with_debts': clients_with_debts,
        'out_of_stock_count': out_of_stock_count,
        'low_stock_count': low_stock_count,
        'total_products': total_products,
        'total_clients': total_clients,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'sales_by_day_labels': sales_by_day_labels,
        'sales_by_day_values': sales_by_day_values,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def generate_report_data(request):
    """Retorna dados do relatório em JSON para exibição na página"""
    # Obter parâmetros de período (padrão: último mês)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        try:
            date_str = request.GET.get('start_date')
            naive_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = timezone.make_aware(naive_date.replace(hour=0, minute=0, second=0, microsecond=0))
        except (ValueError, TypeError):
            pass
    
    if request.GET.get('end_date'):
        try:
            date_str = request.GET.get('end_date')
            naive_date = datetime.strptime(date_str, '%Y-%m-%d')
            end_date = timezone.make_aware(naive_date.replace(hour=23, minute=59, second=59, microsecond=999999))
        except (ValueError, TypeError):
            pass
    
    # Filtrar vendas finalizadas no período
    sales = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Preparar dados para o relatório
    # 1. Vendas por mês
    sales_by_month = defaultdict(Decimal)
    for sale in sales:
        month_key = sale.created_at.strftime('%Y-%m')
        sales_by_month[month_key] += sale.total
    
    # Ordenar por mês
    months_data = sorted(sales_by_month.items())
    months_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    months_labels = [months_pt[int(m.split('-')[1]) - 1] for m, _ in months_data]
    months_values = [float(v) for _, v in months_data]
    
    # 2. Participação por produto
    product_sales = defaultdict(lambda: {'quantity': 0, 'total': Decimal('0.00')})
    for sale in sales:
        for item in sale.items.all():
            product_sales[item.product.name]['quantity'] += item.quantity
            product_sales[item.product.name]['total'] += item.price * item.quantity
    
    # Ordenar produtos por total vendido
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['total'], reverse=True)
    
    # Pegar top 4 produtos e agrupar o resto em "Outros"
    top_products = sorted_products[:4]
    others_total = sum(p[1]['total'] for p in sorted_products[4:])
    others_quantity = sum(p[1]['quantity'] for p in sorted_products[4:])
    
    if others_total > 0:
        top_products.append(('Outros', {'quantity': others_quantity, 'total': others_total}))
    
    # Calcular percentuais
    total_sales = sum(p[1]['total'] for p in product_sales.values())
    product_percentages = []
    product_labels = []
    product_values = []
    product_quantities = []
    
    for name, data in top_products:
        percentage = (data['total'] / total_sales * 100) if total_sales > 0 else 0
        product_percentages.append({
            'name': name,
            'percentage': float(percentage),
            'total': float(data['total']),
            'quantity': data['quantity']
        })
        product_labels.append(name)
        product_values.append(float(data['total']))
        product_quantities.append(data['quantity'])
    
    # 3. Estatísticas gerais
    total_vendas = sales.aggregate(total=Sum(F('items__price') * F('items__quantity')))['total'] or Decimal('0.00')
    total_produtos_vendidos = SaleItem.objects.filter(
        sale__in=sales
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Produto mais vendido
    most_sold_product = None
    if sorted_products:
        most_sold_product = {
            'name': sorted_products[0][0],
            'quantity': sorted_products[0][1]['quantity']
        }
    
    # Produto menos vendido (dos que foram vendidos)
    least_sold_product = None
    if sorted_products and len(sorted_products) > 1:
        least_sold_product = {
            'name': sorted_products[-1][0],
            'quantity': sorted_products[-1][1]['quantity']
        }
    
    # Produtos em falta (quantidade = 0)
    out_of_stock = Product.objects.filter(quantity=0).count()
    
    # Retornar JSON
    return JsonResponse({
        'start_date': start_date.strftime('%d/%m/%Y'),
        'end_date': end_date.strftime('%d/%m/%Y'),
        'months': {
            'labels': months_labels,
            'values': months_values
        },
        'products': {
            'labels': product_labels,
            'values': product_values,
            'quantities': product_quantities,
            'percentages': product_percentages
        },
        'stats': {
            'total_vendas': float(total_vendas),
            'total_produtos_vendidos': total_produtos_vendidos,
            'out_of_stock': out_of_stock,
            'most_sold_product': most_sold_product,
            'least_sold_product': least_sold_product
        }
    })


@login_required
def generate_report_pdf(request):
    """Gera relatório financeiro em PDF"""
    # Obter parâmetros de período (padrão: último mês)
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    if request.GET.get('start_date'):
        try:
            date_str = request.GET.get('start_date')
            naive_date = datetime.strptime(date_str, '%Y-%m-%d')
            # Converter para início do dia no timezone local
            start_date = timezone.make_aware(naive_date.replace(hour=0, minute=0, second=0, microsecond=0))
        except (ValueError, TypeError):
            # Se houver erro, manter a data padrão
            pass
    
    if request.GET.get('end_date'):
        try:
            date_str = request.GET.get('end_date')
            naive_date = datetime.strptime(date_str, '%Y-%m-%d')
            # Converter para fim do dia no timezone local
            end_date = timezone.make_aware(naive_date.replace(hour=23, minute=59, second=59, microsecond=999999))
        except (ValueError, TypeError):
            # Se houver erro, manter a data padrão
            pass
    
    # Filtrar vendas finalizadas no período
    sales = Sale.objects.filter(
        status=Sale.STATUS_FINALIZED,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Preparar dados para o relatório
    # 1. Vendas por mês
    sales_by_month = defaultdict(Decimal)
    for sale in sales:
        month_key = sale.created_at.strftime('%Y-%m')
        sales_by_month[month_key] += sale.total
    
    # Ordenar por mês
    months_data = sorted(sales_by_month.items())
    months_pt = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    months_labels = [months_pt[int(m.split('-')[1]) - 1] for m, _ in months_data]
    months_values = [float(v) for _, v in months_data]
    
    # 2. Participação por produto
    product_sales = defaultdict(lambda: {'quantity': 0, 'total': Decimal('0.00')})
    for sale in sales:
        for item in sale.items.all():
            product_sales[item.product.name]['quantity'] += item.quantity
            product_sales[item.product.name]['total'] += item.price * item.quantity
    
    # Ordenar produtos por total vendido
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['total'], reverse=True)
    
    # Pegar top 4 produtos e agrupar o resto em "Outros"
    top_products = sorted_products[:4]
    others_total = sum(p[1]['total'] for p in sorted_products[4:])
    others_quantity = sum(p[1]['quantity'] for p in sorted_products[4:])
    
    if others_total > 0:
        top_products.append(('Outros', {'quantity': others_quantity, 'total': others_total}))
    
    # Calcular percentuais
    total_sales = sum(p[1]['total'] for p in product_sales.values())
    product_percentages = []
    for name, data in top_products:
        percentage = (data['total'] / total_sales * 100) if total_sales > 0 else 0
        product_percentages.append({
            'name': name,
            'percentage': percentage,
            'total': data['total']
        })
    
    # 3. Estatísticas gerais
    total_vendas = sales.aggregate(total=Sum(F('items__price') * F('items__quantity')))['total'] or Decimal('0.00')
    total_produtos_vendidos = SaleItem.objects.filter(
        sale__in=sales
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Produto mais vendido
    most_sold_product = None
    if sorted_products:
        most_sold_product = sorted_products[0]
    
    # Produto menos vendido (dos que foram vendidos)
    least_sold_product = None
    if sorted_products:
        least_sold_product = sorted_products[-1] if len(sorted_products) > 1 else None
    
    # Produtos em falta (quantidade = 0)
    out_of_stock = Product.objects.filter(quantity=0).count()
    
    # Criar o PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30,
                           topMargin=30, bottomMargin=30)
    
    # Container para os elementos do PDF
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#B91C1C'),  # Vermelho similar ao tema
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#B91C1C'),
        spaceAfter=12,
        spaceBefore=12
    )
    
    # Título
    story.append(Paragraph("Relatório Financeiro", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Período
    period_text = f"Período: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    story.append(Paragraph(period_text, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Estatísticas gerais
    story.append(Paragraph("Estatísticas Gerais", heading_style))
    stats_data = [
        ['Total de Vendas', f"R$ {float(total_vendas):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')],
        ['Total de Produtos Vendidos', f"{total_produtos_vendidos} unidades"],
        ['Produtos em Falta', f"{out_of_stock} produtos"],
    ]
    
    if most_sold_product:
        stats_data.append(['Produto Mais Vendido', f"{most_sold_product[0]} ({most_sold_product[1]['quantity']} unidades)"])
    
    # Mensagem se não houver dados
    if not sales.exists():
        story.append(Paragraph("Não há vendas no período selecionado.", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    stats_table = Table(stats_data, colWidths=[4*inch, 2.5*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEE2E2')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Gráfico de vendas por mês
    if months_data and len(months_data) > 0:
        story.append(Paragraph("Vendas por Mês", heading_style))
        
        # Criar gráfico
        fig, ax = plt.subplots(figsize=(6, 4))
        bars = ax.bar(months_labels, months_values, color='#2563EB', edgecolor='black')
        ax.set_ylabel('Valor (R$)', fontsize=10)
        ax.set_xlabel('Mês', fontsize=10)
        ax.set_title('Vendas por Mês', fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # Adicionar valores nas barras
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'R$ {height:,.0f}'.replace(',', '.'),
                   ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # Converter gráfico para imagem
        canvas = FigureCanvasAgg(fig)
        img_buffer = BytesIO()
        canvas.print_png(img_buffer)
        img_buffer.seek(0)
        plt.close(fig)
        
        # Adicionar imagem ao PDF
        img_buffer.seek(0)
        img = Image(img_buffer, width=5.5*inch, height=3.7*inch)
        story.append(img)
        story.append(Spacer(1, 0.3*inch))
    
    # Participação por produto
    if product_percentages and len(product_percentages) > 0:
        story.append(Paragraph("Participação por Produto", heading_style))
        
        # Tabela de participação
        product_data = [['Produto', 'Participação', 'Total Vendido']]
        colors_list = ['#2563EB', '#F97316', '#10B981', '#06B6D4', '#8B5CF6']
        
        for i, product in enumerate(product_percentages):
            color = colors_list[i % len(colors_list)]
            product_data.append([
                product['name'],
                f"{product['percentage']:.1f}%",
                f"R$ {float(product['total']):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            ])
        
        product_table = Table(product_data, colWidths=[2.5*inch, 2*inch, 2*inch])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B91C1C')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(product_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Gráfico de pizza
        fig, ax = plt.subplots(figsize=(6, 4))
        labels = [p['name'] for p in product_percentages]
        sizes = [p['percentage'] for p in product_percentages]
        # Converter cores hex para matplotlib
        import matplotlib.colors as mcolors
        pie_colors = [mcolors.to_rgba(c) for c in colors_list[:len(product_percentages)]]
        
        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=pie_colors, autopct='%1.1f%%',
                                          startangle=90, textprops={'fontsize': 9})
        
        ax.set_title('Participação por Produto', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # Converter gráfico para imagem
        canvas = FigureCanvasAgg(fig)
        img_buffer2 = BytesIO()
        canvas.print_png(img_buffer2)
        img_buffer2.seek(0)
        plt.close(fig)
        
        # Adicionar imagem ao PDF
        img2 = Image(img_buffer2, width=5.5*inch, height=3.7*inch)
        story.append(img2)
    
    # Rodapé
    story.append(Spacer(1, 0.3*inch))
    footer_text = f"Relatório gerado em {timezone.now().strftime('%d/%m/%Y às %H:%M')}"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], 
                                                        alignment=TA_CENTER, fontSize=9,
                                                        textColor=colors.grey)))
    
    # Construir PDF
    doc.build(story)
    
    # Retornar resposta
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf"'
    
    return response
