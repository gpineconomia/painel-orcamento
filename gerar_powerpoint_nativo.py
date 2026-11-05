"""Gera a Apresentação Executiva da Alta Gestão em PowerPoint Nativo (.pptx) - Widescreen 16:9.
Suporta geração da Versão 2 (Atualizada - Déficit R$ 45,26 Mi) e Versão 1 (Original - Déficit R$ 47,45 Mi).
"""
from __future__ import annotations

import os
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BASE_DIR = Path(__file__).parent
BRAIN_DIR = Path(r"C:\Users\joao.veronez\.gemini\antigravity\brain\1c42b43d-4384-4107-b309-7bf1a885bf28")

# Paleta de Cores Institucionais Goiás / Economia
C_DARK_GREEN = RGBColor(6, 78, 59)     # #064E3B
C_EMERALD    = RGBColor(4, 120, 87)    # #047857
C_LIGHT_MINT = RGBColor(236, 253, 245) # #ECFDF5
C_MINT_BORDER= RGBColor(167, 243, 208) # #A7F3D0
C_WHITE      = RGBColor(255, 255, 255)
C_DARK_SLATE = RGBColor(15, 23, 42)     # #0F172A
C_MUTED_GRAY = RGBColor(100, 116, 139) # #64748B
C_LIGHT_GRAY = RGBColor(248, 250, 252) # #F8FAFC
C_BORDER_GRAY= RGBColor(226, 232, 240) # #E2E8F0
C_ALERT_ROSE = RGBColor(255, 241, 242) # #FFF1F2
C_ALERT_BORDER= RGBColor(254, 205, 211)# #FECDD3
C_ALERT_RED  = RGBColor(225, 29, 72)   # #E11D48
C_AMBER_BG   = RGBColor(254, 243, 199) # #FEF3C7
C_AMBER_TEXT = RGBColor(180, 83, 9)    # #B45309


def build_presentation(version: str = "v2"):
    is_v1 = (version.lower() == "v1")
    deficit_str = "R$ 47,45 Mi" if is_v1 else "R$ 45,26 Mi"
    piso_str    = "R$ 191,54 Mi" if is_v1 else "R$ 189,35 Mi"
    sg_str      = "R$ 5,58 Mi" if is_v1 else "R$ 3,39 Mi"
    sub_tag     = f"ALTA GESTÃO • CENÁRIO 2027 ({'V1 - BASE' if is_v1 else 'V2 - ATUALIZADA'})"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def add_header(slide, tag_text: str, title_text: str, subtitle_text: str = ""):
        # Fundo do slide
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = C_LIGHT_GRAY
        bg.line.fill.background()

        # Barra do Topo
        top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(1.15))
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = C_WHITE
        top_bar.line.color.rgb = C_BORDER_GRAY

        # Badge GO
        badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(0.22), Inches(0.7), Inches(0.7))
        badge.fill.solid()
        badge.fill.fore_color.rgb = C_DARK_GREEN
        badge.line.fill.background()
        tf_b = badge.text_frame
        tf_b.word_wrap = True
        p_b = tf_b.paragraphs[0]
        p_b.text = "GO"
        p_b.font.bold = True
        p_b.font.size = Pt(14)
        p_b.font.color.rgb = C_WHITE
        p_b.alignment = PP_ALIGN.CENTER

        # Título do Topo
        tx_box = slide.shapes.add_textbox(Inches(1.45), Inches(0.18), Inches(7.5), Inches(0.8))
        tf = tx_box.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = "SECRETARIA DA ECONOMIA • ESTADO DE GOIÁS"
        p0.font.size = Pt(9.5)
        p0.font.bold = True
        p0.font.color.rgb = C_DARK_GREEN

        p1 = tf.add_paragraph()
        p1.text = title_text
        p1.font.size = Pt(14)
        p1.font.bold = True
        p1.font.color.rgb = C_DARK_SLATE

        # Tag Categoria à Direita
        tag_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.2), Inches(0.32), Inches(3.5), Inches(0.48))
        tag_box.fill.solid()
        tag_box.fill.fore_color.rgb = C_LIGHT_MINT
        tag_box.line.color.rgb = C_MINT_BORDER
        tf_t = tag_box.text_frame
        p_t = tf_t.paragraphs[0]
        p_t.text = tag_text
        p_t.font.size = Pt(9.5)
        p_t.font.bold = True
        p_t.font.color.rgb = C_DARK_GREEN
        p_t.alignment = PP_ALIGN.CENTER

        # Subtítulo (abaixo da barra branca)
        if subtitle_text:
            sub_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.22), Inches(12.1), Inches(0.45))
            tf_s = sub_box.text_frame
            tf_s.word_wrap = True
            p_s = tf_s.paragraphs[0]
            p_s.text = subtitle_text
            p_s.font.size = Pt(11)
            p_s.font.color.rgb = C_MUTED_GRAY

        # Rodapé
        ft_box = slide.shapes.add_textbox(Inches(0.6), Inches(7.1), Inches(12.1), Inches(0.35))
        tf_f = ft_box.text_frame
        p_f = tf_f.paragraphs[0]
        p_f.text = f"Fonte Oficial: SIAFIC • PLOA 2027 • Gerência de Planejamento e Orçamento (GPIN/ECONOMIA) • {sub_tag}"
        p_f.font.size = Pt(8.5)
        p_f.font.color.rgb = C_MUTED_GRAY

    # =========================================================================
    # SLIDE 1: CAPA EXECUTIVA
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = C_DARK_GREEN
    bg1.line.fill.background()

    # Badge Topo
    badge1 = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(1.4), Inches(5.0), Inches(0.5))
    badge1.fill.solid()
    badge1.fill.fore_color.rgb = RGBColor(6, 95, 70)
    badge1.line.color.rgb = RGBColor(52, 211, 153)
    tf_b1 = badge1.text_frame
    p_b1 = tf_b1.paragraphs[0]
    p_b1.text = f"DIAGNÓSTICO ORÇAMENTÁRIO • EXERCÍCIO 2027 ({'V1' if is_v1 else 'V2'})"
    p_b1.font.bold = True
    p_b1.font.size = Pt(10)
    p_b1.font.color.rgb = RGBColor(209, 250, 229)
    p_b1.alignment = PP_ALIGN.CENTER

    # Título Principal
    t1_box = s1.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(11.3), Inches(1.8))
    tf1 = t1_box.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "O Desafio da Cota Orçamentária 2027"
    p1.font.size = Pt(36)
    p1.font.bold = True
    p1.font.color.rgb = C_WHITE

    p1_sub = tf1.add_paragraph()
    p1_sub.text = f"O desafio de adequação e corte orçamentário diante da cota fixada na PLOA 2027 (R$ 144,1 Mi) e da predominância de despesas de caráter continuado."
    p1_sub.font.size = Pt(17)
    p1_sub.font.color.rgb = RGBColor(209, 250, 229)

    # Cards Resumo na Capa
    card_data = [
        ("COTA PLOA 2027", "R$ 144,10 Mi", "Teto fixado para o exercício"),
        ("NECESSIDADE REAL", piso_str, "Piso mínimo incompressível"),
        ("DÉFICIT MAPEADO", deficit_str, "Descobertura a suplementar"),
    ]
    for idx, (lbl, val, desc) in enumerate(card_data):
        cx = Inches(1.0 + idx * 3.8)
        c_shape = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(4.5), Inches(3.6), Inches(1.8))
        c_shape.fill.solid()
        c_shape.fill.fore_color.rgb = RGBColor(4, 120, 87)
        c_shape.line.color.rgb = RGBColor(16, 185, 129)
        c_tf = c_shape.text_frame
        c_tf.word_wrap = True
        
        cp0 = c_tf.paragraphs[0]
        cp0.text = lbl
        cp0.font.size = Pt(10)
        cp0.font.bold = True
        cp0.font.color.rgb = RGBColor(167, 243, 208)
        
        cp1 = c_tf.add_paragraph()
        cp1.text = val
        cp1.font.size = Pt(22)
        cp1.font.bold = True
        cp1.font.color.rgb = C_WHITE
        
        cp2 = c_tf.add_paragraph()
        cp2.text = desc
        cp2.font.size = Pt(9.5)
        cp2.font.color.rgb = RGBColor(209, 250, 229)

    # =========================================================================
    # SLIDE 2: EVOLUÇÃO DA COTA ORÇAMENTÁRIA (2024-2027)
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "HISTÓRICO DE COTAS (2024–2027)", "Evolução da Cota Orçamentária Disponibilizada", "Comparativo das cotas fixadas ao final de cada exercício e o recuo severo na PLOA 2027.")

    cotas = [
        ("COTA 2024", "R$ 155,1 Mi", "R$ 155.094.475,00", "Base Histórica", C_BORDER_GRAY, C_DARK_SLATE),
        ("COTA 2025", "R$ 185,8 Mi", "R$ 185.848.369,24", "+19,8% vs 2024", C_BORDER_GRAY, C_DARK_SLATE),
        ("COTA 2026", "R$ 207,5 Mi", "R$ 207.478.836,89", "+11,6% (Recorde)", C_MINT_BORDER, C_EMERALD),
        ("COTA 2027 (PLOA)", "R$ 144,1 Mi", "R$ 144.095.319,00", "-30,5% (-R$ 63,4 Mi)", C_ALERT_BORDER, C_ALERT_RED),
    ]
    for i, (titulo, val, full_val, variacao, b_color, t_color) in enumerate(cotas):
        cx = Inches(0.6 + i * 3.05)
        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(2.9), Inches(3.2))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = b_color
        card.line.width = Pt(1.5)
        tf = card.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = titulo
        p0.font.bold = True
        p0.font.size = Pt(11)
        p0.font.color.rgb = C_MUTED_GRAY

        p1 = tf.add_paragraph()
        p1.text = val
        p1.font.bold = True
        p1.font.size = Pt(24)
        p1.font.color.rgb = t_color

        p2 = tf.add_paragraph()
        p2.text = full_val
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_MUTED_GRAY

        p3 = tf.add_paragraph()
        p3.text = f"\n{variacao}"
        p3.font.bold = True
        p3.font.size = Pt(11)
        p3.font.color.rgb = t_color

    box2 = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.2), Inches(12.1), Inches(1.6))
    box2.fill.solid()
    box2.fill.fore_color.rgb = C_ALERT_ROSE
    box2.line.color.rgb = C_ALERT_BORDER
    tf_b2 = box2.text_frame
    tf_b2.word_wrap = True
    pb2 = tf_b2.paragraphs[0]
    pb2.text = "ANÁLISE DE IMPACTO E REGRESSÃO ORÇAMENTÁRIA:"
    pb2.font.bold = True
    pb2.font.size = Pt(11)
    pb2.font.color.rgb = C_ALERT_RED
    pb2_desc = tf_b2.add_paragraph()
    pb2_desc.text = "A cota proposta para 2027 representa uma regressão orçamentária severa de R$ 63,4 Mi (-30,5%) em relação a 2026. A Pasta fica R$ 11,0 Mi abaixo até mesmo do nível executado em 2024, apesar do expressivo aumento dos custos de tecnologia, limpeza e suporte operacional decorrentes dos investimentos implantados nos últimos anos."
    pb2_desc.font.size = Pt(10.5)
    pb2_desc.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 3: O NÚMERO MÁGICO DA NECESSIDADE
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "DIAGNÓSTICO E GAP DE RECURSOS", f"O Número Mágico da Necessidade ({piso_str}) vs. Cota PLOA", "Cálculo detalhado do piso incompressível essencial e a descoberta projetada.")

    s3_cards = [
        ("PISO INCOMPRESSÍVEL (NECESSIDADE REAL)", piso_str, "Mínimo indispensável para honrar despesas continuadas pactuadas e manter o funcionamento de postos e sistemas.", C_MINT_BORDER, C_EMERALD, C_LIGHT_MINT),
        ("COTA FIXADA NA PLOA 2027", "R$ 144,10 Mi", "Teto preliminar disponibilizado pelo Tesouro Estadual, insuficiente para o ciclo anual completo.", C_BORDER_GRAY, C_DARK_SLATE, C_WHITE),
        ("DÉFICIT MAPEADO A SUPLEMENTAR", deficit_str, "Descobertura orçamentária mapeada que exigirá suplementação formal tempestiva no decorrer do exercício.", C_ALERT_BORDER, C_ALERT_RED, C_ALERT_ROSE),
    ]
    for i, (tit, val, desc, b_col, t_col, bg_col) in enumerate(s3_cards):
        cx = Inches(0.6 + i * 4.1)
        card = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(3.9), Inches(3.2))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_col
        card.line.color.rgb = b_col
        card.line.width = Pt(1.5)
        tf = card.text_frame
        tf.word_wrap = True

        p0 = tf.paragraphs[0]
        p0.text = tit
        p0.font.bold = True
        p0.font.size = Pt(10.5)
        p0.font.color.rgb = t_col

        p1 = tf.add_paragraph()
        p1.text = val
        p1.font.bold = True
        p1.font.size = Pt(28)
        p1.font.color.rgb = t_col

        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(10)
        p2.font.color.rgb = C_DARK_SLATE

    box3 = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.2), Inches(12.1), Inches(1.6))
    box3.fill.solid()
    box3.fill.fore_color.rgb = C_WHITE
    box3.line.color.rgb = C_BORDER_GRAY
    tf_b3 = box3.text_frame
    tf_b3.word_wrap = True
    p3 = tf_b3.paragraphs[0]
    p3.text = f"COMPOSIÇÃO DO PISO INCOMPRESSÍVEL ({piso_str}):"
    p3.font.bold = True
    p3.font.size = Pt(11)
    p3.font.color.rgb = C_DARK_GREEN
    p3_desc = tf_b3.add_paragraph()
    p3_desc.text = f"• Custeio Continuado Administrativo: R$ 158,54 Mi (Folha terceirizada, energia, água, vigilância armada, limpeza predial e contratos de suporte aos postos).\n• TIC Essencial: R$ 25,23 Mi (Links dedicados de alta resiliência, datacenter, nuvem governamental, banco de dados e suporte ao SIAFIC).\n• Demais Contratos Inadiáveis e Serviços Gerais: {sg_str} (Adequações de contratos reduzidos ao limite técnico estrito)."
    p3_desc.font.size = Pt(10)
    p3_desc.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 4: SUPRESSÕES PROPOSTAS NA PLOA 2027
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "ESFORÇO PRÉVIO DE CONTENÇÃO", "Supressões Propostas na PLOA 2027: O Limite da Compressão", "Demonstração das reduções contratuais já absorvidas internamente pela Pasta.")

    tot_card = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.8), Inches(3.6), Inches(5.0))
    tot_card.fill.solid()
    tot_card.fill.fore_color.rgb = C_DARK_GREEN
    tot_card.line.fill.background()
    tf_tot = tot_card.text_frame
    tf_tot.word_wrap = True
    pt0 = tf_tot.paragraphs[0]
    pt0.text = "ESFORÇO INTERNO CONCLUÍDO"
    pt0.font.size = Pt(10)
    pt0.font.bold = True
    pt0.font.color.rgb = RGBColor(167, 243, 208)

    pt1 = tf_tot.add_paragraph()
    pt1.text = "R$ 38,4 Mi"
    pt1.font.size = Pt(32)
    pt1.font.bold = True
    pt1.font.color.rgb = C_WHITE

    pt2 = tf_tot.add_paragraph()
    pt2.text = "Total de cortes e supressões contratuais já pactuados pela Economia com fornecedores e áreas técnicas para viabilizar a proposta orçamentária."
    pt2.font.size = Pt(10.5)
    pt2.font.color.rgb = RGBColor(209, 250, 229)

    pt3 = tf_tot.add_paragraph()
    pt3.text = "\n⚠️ Limite da Compressão:\nQualquer corte adicional paralisa serviços públicos essenciais, atendimento tributário ao contribuinte e sistemas de fiscalização em fronteira."
    pt3.font.size = Pt(10)
    pt3.font.color.rgb = RGBColor(254, 205, 211)

    sup_items = [
        ("Desenvolvimento e Sustentação de TIC", "R$ 14,2 Mi", "Redução drástica de fábrica de software e novas customizações não prioritárias."),
        ("Serviços Gerais, Recepção e Apoio Operacional", "R$ 4,8 Mi", "Renegociação de postos de trabalho e racionalização do efetivo terceirizado."),
        ("Licenciamento de Software e Ambientes em Nuvem", "R$ 3,9 Mi", "Otimização de consumo computacional e supressão de licenças de uso secundárias."),
        ("Locação de Veículos e Frotas de Fiscalização", "R$ 2,5 Mi", "Devolução de veículos administrativos e foco exclusivo na fiscalização operacional."),
        ("Outras Despesas e Contratos Operacionais", "R$ 13,0 Mi", "Corte severo em materiais permanentes, eventos, consultorias e diárias discricionárias."),
    ]
    for idx, (nome, valor, desc) in enumerate(sup_items):
        sy = Inches(1.8 + idx * 1.0)
        sc = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.4), sy, Inches(8.3), Inches(0.88))
        sc.fill.solid()
        sc.fill.fore_color.rgb = C_WHITE
        sc.line.color.rgb = C_BORDER_GRAY
        tf_s = sc.text_frame
        tf_s.word_wrap = True
        
        ps0 = tf_s.paragraphs[0]
        ps0.text = f"{nome}  •  "
        ps0.font.bold = True
        ps0.font.size = Pt(11)
        ps0.font.color.rgb = C_DARK_SLATE
        run_v = ps0.add_run()
        run_v.text = f"-{valor}"
        run_v.font.bold = True
        run_v.font.color.rgb = C_ALERT_RED

        ps1 = tf_s.add_paragraph()
        ps1.text = desc
        ps1.font.size = Pt(9)
        ps1.font.color.rgb = C_MUTED_GRAY

    # =========================================================================
    # SLIDE 5: TRANSIÇÃO DE INVESTIMENTOS PARA GESTÃO E MANUTENÇÃO
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "EVIDÊNCIA ORÇAMENTÁRIA • SIAFIC", "Transição de Investimentos para Gestão e Manutenção", "Como os grandes investimentos entregues no ciclo anterior se transformaram em despesas fixas.")

    c1 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.8), Inches(5.9), Inches(4.1))
    c1.fill.solid()
    c1.fill.fore_color.rgb = C_WHITE
    c1.line.color.rgb = C_BORDER_GRAY
    tf1 = c1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "CICLO ANTERIOR (2023–2025): FASE DE IMPLANTAÇÃO"
    p1.font.bold = True
    p1.font.size = Pt(11)
    p1.font.color.rgb = C_DARK_GREEN
    p1_desc = tf1.add_paragraph()
    p1_desc.text = "• Grandes aquisições de equipamentos e servidores de alta densidade.\n• Implantação e customização de novos módulos tributários e do SIAFIC.\n• Modernização física e predial das delegacias e postos fiscais de divisa.\n• Orçamento concentrado em GND 4 (Investimentos), financiado com recursos extraordinários e convênios."
    p1_desc.font.size = Pt(10.5)
    p1_desc.font.color.rgb = C_DARK_SLATE

    c2 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.9), Inches(4.1))
    c2.fill.solid()
    c2.fill.fore_color.rgb = C_WHITE
    c2.line.color.rgb = C_BORDER_GRAY
    tf2 = c2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "CICLO ATUAL (2026–2027): FASE DE OPERAÇÃO E SUSTENTAÇÃO"
    p2.font.bold = True
    p2.font.size = Pt(11)
    p2.font.color.rgb = C_ALERT_RED
    p2_desc = tf2.add_paragraph()
    p2_desc.text = "• Custos obrigatórios de manutenção preventiva, garantia estendida e suporte 24/7.\n• Licenciamento contínuo de softwares corporativos e links de comunicação.\n• Despesas de energia elétrica, refrigeração e segurança de datacenters.\n• Todo o gasto migra estruturalmente para GND 3 (Custeio Continuado).\n• A interrupção desses pagamentos inutiliza os investimentos milionários já realizados."
    p2_desc.font.size = Pt(10.5)
    p2_desc.font.color.rgb = C_DARK_SLATE

    box5 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(6.05), Inches(12.1), Inches(0.9))
    box5.fill.solid()
    box5.fill.fore_color.rgb = C_LIGHT_MINT
    box5.line.color.rgb = C_MINT_BORDER
    tf5 = box5.text_frame
    tf5.word_wrap = True
    p5 = tf5.paragraphs[0]
    p5.text = "💡 Síntese Técnica: 'Investimento concluído não desaparece: ele se transforma obrigatoriamente em custeio permanente de sustentação e manutenção operacional.'"
    p5.font.bold = True
    p5.font.size = Pt(11)
    p5.font.color.rgb = C_DARK_GREEN

    # =========================================================================
    # SLIDE 6: DINÂMICA E EXECUÇÃO DO CUSTEIO EM 2026
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "EXECUÇÃO ORÇAMENTÁRIA 2026 • SIAFIC ATÉ 04/11/2026", "Dinâmica e Execução do Custeio em 2026", "Ritmo de empenho e liquidação do custeio e o papel dos Restos a Pagar (RAP).")

    kpi6 = [
        ("COTA 2026 TOTAL", "R$ 207,48 Mi", "100% da cota disponibilizada"),
        ("EMPENHADO 2026", "R$ 184,32 Mi", "88,8% da cota comprometida"),
        ("LIQUIDADO 2026", "R$ 142,10 Mi", "68,5% das despesas atestadas"),
        ("RESTOS A PAGAR (RAP)", "R$ 42,22 Mi", "Empenhados a liquidar até o encerramento"),
    ]
    for i, (t, v, sub) in enumerate(kpi6):
        cx = Inches(0.6 + i * 3.05)
        card = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(2.9), Inches(2.4))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = t
        p0.font.bold = True
        p0.font.size = Pt(10.5)
        p0.font.color.rgb = C_MUTED_GRAY
        p1 = tf.add_paragraph()
        p1.text = v
        p1.font.bold = True
        p1.font.size = Pt(22)
        p1.font.color.rgb = C_DARK_GREEN if i < 3 else C_AMBER_TEXT
        p2 = tf.add_paragraph()
        p2.text = sub
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = C_DARK_SLATE

    box6 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(4.45), Inches(12.1), Inches(2.4))
    box6.fill.solid()
    box6.fill.fore_color.rgb = C_WHITE
    box6.line.color.rgb = C_BORDER_GRAY
    tf6 = box6.text_frame
    tf6.word_wrap = True
    p6_0 = tf6.paragraphs[0]
    p6_0.text = "OBSERVAÇÕES ESTRUTURAIS SOBRE O CUSTEIO E RESTOS A PAGAR (RAP):"
    p6_0.font.bold = True
    p6_0.font.size = Pt(11)
    p6_0.font.color.rgb = C_DARK_GREEN
    p6_desc = tf6.add_paragraph()
    p6_desc.text = "1. Consumo Regular: A execução do custeio apresenta regularidade estrita, com média de consumo de R$ 14,2 Mi a R$ 15,5 Mi por mês, comprovando a incompressibilidade da máquina fiscal.\n2. Restos a Pagar (RAP): A diferença entre empenho (R$ 184,32 Mi) e liquidação (R$ 142,10 Mi) decorre do fluxo natural de atesto e medição de notas fiscais nos meses de novembro e dezembro.\n3. Alerta 2027: A cota PLOA 2027 de R$ 144,1 Mi mal alcança o montante já liquidado em 10 meses de 2026 (R$ 142,1 Mi), ignorando que o ano de 2027 terá 12 meses de despesas cheias."
    p6_desc.font.size = Pt(10)
    p6_desc.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 7: DIFICULDADES NA LIQUIDAÇÃO DE INVESTIMENTOS EM 2026
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_header(s7, "EXECUÇÃO ORÇAMENTÁRIA 2026 • SIAFIC", "Dificuldades na Liquidação de Investimentos em 2026", "Fatores operacionais que explicam o descompasso entre empenho e liquidação de capital.")

    c7_1 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.8), Inches(4.0), Inches(5.0))
    c7_1.fill.solid()
    c7_1.fill.fore_color.rgb = C_WHITE
    c7_1.line.color.rgb = C_BORDER_GRAY
    tf7_1 = c7_1.text_frame
    tf7_1.word_wrap = True
    p7_1 = tf7_1.paragraphs[0]
    p7_1.text = "QUADRO DE INVESTIMENTOS 2026"
    p7_1.font.bold = True
    p7_1.font.size = Pt(11)
    p7_1.font.color.rgb = C_DARK_SLATE
    
    p7_v1 = tf7_1.add_paragraph()
    p7_v1.text = "R$ 28,50 Mi\nOrçado em Investimentos"
    p7_v1.font.size = Pt(14)
    p7_v1.font.bold = True
    p7_v1.font.color.rgb = C_EMERALD

    p7_v2 = tf7_1.add_paragraph()
    p7_v2.text = "\nR$ 8,12 Mi\nLiquidado até 04/11 (28,5%)"
    p7_v2.font.size = Pt(14)
    p7_v2.font.bold = True
    p7_v2.font.color.rgb = C_ALERT_RED

    p7_v3 = tf7_1.add_paragraph()
    p7_v3.text = "\nTaxa de liquidação muito inferior à do custeio (que atinge 68,5%)."
    p7_v3.font.size = Pt(10)
    p7_v3.font.color.rgb = C_MUTED_GRAY

    gargalos = [
        ("1. Prazos Dilatados de Fabricação e Entrega", "Equipamentos de alta tecnologia (switches de core, servidores e nobreaks industriais) dependem de cadeias globais com prazos de entrega que superam 120 dias após a emissão da Ordem de Fornecimento."),
        ("2. Ritos Estritos de Homologação e Testes", "Atestos técnicos de soluções de software e segurança cibernética exigem testes de estresse em ambiente de homologação antes da liberação do pagamento final."),
        ("3. Conformidade Legal e Certidões", "Exigências fiscais da Lei 14.133 impedem a liquidação em caso de pendências cadastrais transitórias de fornecedores, concentrando as medições nos meses finais do exercício."),
    ]
    for idx, (titulo, desc) in enumerate(gargalos):
        gy = Inches(1.8 + idx * 1.65)
        gc = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.8), gy, Inches(7.9), Inches(1.45))
        gc.fill.solid()
        gc.fill.fore_color.rgb = C_WHITE
        gc.line.color.rgb = C_BORDER_GRAY
        tf_g = gc.text_frame
        tf_g.word_wrap = True
        pg0 = tf_g.paragraphs[0]
        pg0.text = titulo
        pg0.font.bold = True
        pg0.font.size = Pt(11)
        pg0.font.color.rgb = C_DARK_GREEN
        pg1 = tf_g.add_paragraph()
        pg1.text = desc
        pg1.font.size = Pt(9.5)
        pg1.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 8: COMPOSIÇÃO DA COTA 2027: PREDOMINÂNCIA DO CUSTEIO
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_header(s8, "ESTRUTURA ORÇAMENTÁRIA • LOA 2027", "Composição da Cota 2027: Predominância Absoluta do Custeio", "Divisão por Grupo de Natureza de Despesa evidencia ausência de espaço para investimentos.")

    card8_1 = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(1.8), Inches(5.9), Inches(3.4))
    card8_1.fill.solid()
    card8_1.fill.fore_color.rgb = C_WHITE
    card8_1.line.color.rgb = C_EMERALD
    card8_1.line.width = Pt(2)
    tf8_1 = card8_1.text_frame
    tf8_1.word_wrap = True
    p8_1 = tf8_1.paragraphs[0]
    p8_1.text = "GND 3: OUTRAS DESPESAS CORRENTES (CUSTEIO)"
    p8_1.font.bold = True
    p8_1.font.size = Pt(11)
    p8_1.font.color.rgb = C_DARK_GREEN
    p8_v1 = tf8_1.add_paragraph()
    p8_v1.text = "96,2%  (R$ 138,62 Mi)"
    p8_v1.font.size = Pt(26)
    p8_v1.font.bold = True
    p8_v1.font.color.rgb = C_DARK_GREEN
    p8_d1 = tf8_1.add_paragraph()
    p8_d1.text = "Todo o orçamento operacional está voltado para despesas de manutenção da máquina pública estadual: limpeza, vigilância, água, luz, links e suporte contínuo."
    p8_d1.font.size = Pt(10)
    p8_d1.font.color.rgb = C_DARK_SLATE

    card8_2 = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.8), Inches(5.9), Inches(3.4))
    card8_2.fill.solid()
    card8_2.fill.fore_color.rgb = C_WHITE
    card8_2.line.color.rgb = C_BORDER_GRAY
    tf8_2 = card8_2.text_frame
    tf8_2.word_wrap = True
    p8_2 = tf8_2.paragraphs[0]
    p8_2.text = "GND 4: INVESTIMENTOS (CAPITAL)"
    p8_2.font.bold = True
    p8_2.font.size = Pt(11)
    p8_2.font.color.rgb = C_MUTED_GRAY
    p8_v2 = tf8_2.add_paragraph()
    p8_v2.text = "3,8%  (R$ 5,48 Mi)"
    p8_v2.font.size = Pt(26)
    p8_v2.font.bold = True
    p8_v2.font.color.rgb = C_MUTED_GRAY
    p8_d2 = tf8_2.add_paragraph()
    p8_d2.text = "Espaço residual. Insuficiente para qualquer expansão tecnológica de porte, renovação de parques computacionais ou reformas estruturais em postos fiscais."
    p8_d2.font.size = Pt(10)
    p8_d2.font.color.rgb = C_DARK_SLATE

    box8 = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.4), Inches(12.1), Inches(1.5))
    box8.fill.solid()
    box8.fill.fore_color.rgb = C_LIGHT_MINT
    box8.line.color.rgb = C_MINT_BORDER
    tf_b8 = box8.text_frame
    tf_b8.word_wrap = True
    p8_c = tf_b8.paragraphs[0]
    p8_c.text = "CONCLUSÃO ORÇAMENTÁRIA:"
    p8_c.font.bold = True
    p8_c.font.size = Pt(11)
    p8_c.font.color.rgb = C_DARK_GREEN
    p8_cd = tf_b8.add_paragraph()
    p8_cd.text = "O orçamento da Secretaria da Economia em 2027 é de sobrevivência estrita. Como 96,2% é custeio rígido, qualquer corte imposto à pasta significa necessariamente atrasar faturas de serviços essenciais contratados."
    p8_cd.font.size = Pt(10.5)
    p8_cd.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 9: POR QUE É DIFÍCIL CORTAR ORÇAMENTO EM 2027?
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_header(s9, "INFLEXIBILIDADE DA DESPESA", "Por que é Difícil Cortar Orçamento em 2027?", "Pilares de rigidez operacional e jurídica que impedem novos cortes na Secretaria.")

    pilares = [
        ("1. Rigidez Jurídica Contratual", "Contratos de prestação de serviços continuados sob a Lei 14.133 possuem cláusulas obrigatórias de reajuste anual por índices de inflação (IPCA/IGP-M) e repactuação de convenções coletivas de trabalho."),
        ("2. Continuidade da Arrecadação", "A fiscalização tributária e os postos fiscais de fronteira operam em escala ininterrupta 24 horas por dia, 7 dias por semana. Cortes paralisam a arrecadação de ICMS do Estado."),
        ("3. Dependência Crítica de TIC", "Sistemas como Nota Fiscal Eletrônica (NF-e), EFD, SIAFIC e portal do contribuinte exigem links redundantes e servidores ativos. Uma hora de indisponibilidade causa perdas imediatas."),
        ("4. Reajustes e Custos Inflacionários", "O custo unitário de insumos (energia elétrica, combustível e software internacional cotado em dólar) registrou alta superior às correções gerais das cotas orçamentárias."),
    ]
    for i, (titulo, desc) in enumerate(pilares):
        col = i % 2
        row = i // 2
        px = Inches(0.6 + col * 6.2)
        py = Inches(1.8 + row * 2.5)
        card = s9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px, py, Inches(5.9), Inches(2.3))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = titulo
        p0.font.bold = True
        p0.font.size = Pt(12)
        p0.font.color.rgb = C_DARK_GREEN
        p1 = tf.add_paragraph()
        p1.text = desc
        p1.font.size = Pt(10)
        p1.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 10: NECESSIDADE DE CRÉDITO ADICIONAL (LINHA DO TEMPO TRIMESTRAL)
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_header(s10, "CRONOGRAMA DE SUPLEMENTAÇÃO • 2027", "Necessidade de Crédito Adicional Prevista: Linha do Tempo", "Trajetória projetada do consumo orçamentário e a janela mandatória para suplementação.")

    trimestres = [
        ("1º TRIMESTRE (JAN–MAR)", "R$ 48,2 Mi", "Consumo Inicial", "Abertura do exercício, empenhos ordinários de contratos continuados e manutenção básica.", C_BORDER_GRAY, C_DARK_SLATE),
        ("2º TRIMESTRE (ABR–JUN)", "R$ 51,5 Mi", "Pressão Operacional", "Maturação dos contratos de TI e limpeza predial. A cota inicial atinge 69% de comprometimento.", C_BORDER_GRAY, C_DARK_SLATE),
        ("3º TRIMESTRE (JUL–SET)", "R$ 44,4 Mi", "ESGOTAMENTO DA COTA", "A cota PLOA (R$ 144,1 Mi) esgota-se integralmente em Agosto/2027. Início da descobertura.", C_AMBER_BG, C_AMBER_TEXT),
        ("4º TRIMESTRE (OUT–DEZ)", deficit_str, "DÉFICIT MANDATÓRIO", "Necessidade estrita do crédito adicional para honrar o encerramento das contas fiscais.", C_ALERT_ROSE, C_ALERT_RED),
    ]
    for i, (tit, val, status, desc, bg_c, t_c) in enumerate(trimestres):
        cx = Inches(0.6 + i * 3.05)
        card = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(2.9), Inches(3.5))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_c
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = tit
        p0.font.bold = True
        p0.font.size = Pt(10)
        p0.font.color.rgb = t_c

        p1 = tf.add_paragraph()
        p1.text = val
        p1.font.bold = True
        p1.font.size = Pt(22)
        p1.font.color.rgb = t_c

        p2 = tf.add_paragraph()
        p2.text = status
        p2.font.bold = True
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = t_c

        p3 = tf.add_paragraph()
        p3.text = f"\n{desc}"
        p3.font.size = Pt(9.5)
        p3.font.color.rgb = C_DARK_SLATE

    obs_box = s10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.5), Inches(12.1), Inches(1.4))
    obs_box.fill.solid()
    obs_box.fill.fore_color.rgb = C_AMBER_BG
    obs_box.line.color.rgb = RGBColor(245, 158, 11)
    obs_box.line.width = Pt(1.5)
    tf_obs = obs_box.text_frame
    tf_obs.word_wrap = True
    p_ob0 = tf_obs.paragraphs[0]
    p_ob0.text = "⚠️ OBSERVAÇÃO CRÍTICA PARA A ALTA GESTÃO:"
    p_ob0.font.bold = True
    p_ob0.font.size = Pt(11)
    p_ob0.font.color.rgb = C_AMBER_TEXT
    p_ob1 = tf_obs.add_paragraph()
    p_ob1.text = f"O déficit total mapeado de {deficit_str} depende diretamente do êxito integral das supressões pactuadas (R$ 38,4 Mi). Caso alguma das supressões propostas não se concretize juridicamente ou seja revertida administrativamente, o déficit orçamentário a suplementar aumentará na mesma proporção."
    p_ob1.font.bold = True
    p_ob1.font.size = Pt(10)
    p_ob1.font.color.rgb = C_DARK_SLATE

    # =========================================================================
    # SLIDE 11: LINHA DO TEMPO DETALHADA DO DÉFICIT ORÇAMENTÁRIO
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_header(s11, "DETALHAMENTO ANALÍTICO • EXERCÍCIO 2027", "Linha do Tempo Detalhada do Déficit Orçamentário", "Discriminação detalhada das despesas de déficit por data/mês e contrato.")

    periodos = [
        ("IMEDIATO / CONTRATOS", "R$ 3,74 Mi", "8,3% do déficit", "Business Analytics, IA em Nuvem e SAP"),
        ("JANEIRO / 2027", "R$ 24,16 Mi", "53,4% do déficit", "Terceirização TIC, SEFAZ/RS e GOVTECH"),
        ("FEVEREIRO / 2027", "R$ 9,06 Mi" if not is_v1 else "R$ 11,25 Mi", "20,0% do déficit", f"Serviços Gerais ({sg_str}), OCR Trânsito e Call Center"),
        ("MARÇO A DEZEMBRO", "R$ 8,30 Mi", "18,3% do déficit", "Prorrogações contratuais, apoio e links"),
    ]
    for i, (p_tit, p_val, p_perc, p_sub) in enumerate(periodos):
        cx = Inches(0.6 + i * 3.05)
        card = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(2.9), Inches(1.8))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = p_tit
        p0.font.bold = True
        p0.font.size = Pt(9.5)
        p0.font.color.rgb = C_MUTED_GRAY

        p1 = tf.add_paragraph()
        p1.text = p_val
        p1.font.bold = True
        p1.font.size = Pt(18)
        p1.font.color.rgb = C_ALERT_RED

        p2 = tf.add_paragraph()
        p2.text = f"{p_perc} • {p_sub}"
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = C_DARK_SLATE

    detalhes_deficit = [
        ("Imediato", "R$ 3,74 Mi", "Business Analytics (R$ 3,10 Mi), IA em Nuvem (R$ 0,49 Mi) e SAP (R$ 0,15 Mi)"),
        ("Janeiro / 2027", "R$ 24,16 Mi", "Terceirização TIC - Desenvolvimento de Software (R$ 22,95 Mi), Convênio SEFAZ/RS (R$ 0,51 Mi) e GOVTECH (R$ 0,36 Mi)"),
        ("Fevereiro / 2027", "R$ 9,06 Mi" if not is_v1 else "R$ 11,25 Mi", f"Serviços Gerais e Limpeza ({sg_str}), OCR Fixo de Trânsito (R$ 3,38 Mi) e Call Center de Atendimento (R$ 2,28 Mi)"),
        ("Março a Dezembro", "R$ 8,30 Mi", "Prorrogações de Apoio Operacional, Links Dedicados e Sustentação Microsoft"),
    ]
    for idx, (dt, val, desc) in enumerate(detalhes_deficit):
        dy = Inches(3.8 + idx * 0.78)
        d_card = s11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), dy, Inches(12.1), Inches(0.7))
        d_card.fill.solid()
        d_card.fill.fore_color.rgb = C_WHITE
        d_card.line.color.rgb = C_BORDER_GRAY
        tf_d = d_card.text_frame
        tf_d.word_wrap = True
        pd0 = tf_d.paragraphs[0]
        pd0.text = f"● {dt}  —  "
        pd0.font.bold = True
        pd0.font.size = Pt(11)
        pd0.font.color.rgb = C_DARK_SLATE
        r_v = pd0.add_run()
        r_v.text = f"{val}  |  "
        r_v.font.bold = True
        r_v.font.color.rgb = C_ALERT_RED
        r_d = pd0.add_run()
        r_d.text = desc
        r_d.font.size = Pt(9.5)
        r_d.font.color.rgb = C_MUTED_GRAY

    # =========================================================================
    # SLIDE 12: SÍNTESE TÉCNICA E REFLEXÃO PARA A GESTÃO
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_header(s12, "TOMADA DE DECISÃO ESTRATÉGICA", "Síntese Técnica e Reflexão para a Gestão", "Três conclusões centrais que fundamentam a decisão da Alta Gestão.")

    sinteses = [
        ("1. INSUFICIÊNCIA DA COTA PLOA", "A cota de R$ 144,1 Mi não cobre os 12 meses do ano civil de 2027.", "O valor disponibilizado cobre apenas até o início do mês de agosto/2027. Manter a proposta sem previsão de suplementação resultará em inadimplência contratual no segundo semestre."),
        ("2. ESGOTAMENTO DO ESFORÇO INTERNO", "O corte prévio de R$ 38,4 Mi atingiu o limite técnico incompressível.", "A Pasta já eliminou todos os investimentos discricionários e reduziu postos de trabalho terceirizados. Cortes adicionais afetarão diretamente os sistemas de arrecadação do Estado."),
        ("3. TEMPESTIVIDADE DA SUPLEMENTAÇÃO", f"A pactuação prévia de {deficit_str} evita paralisações e passivo de RAP.", "Garante segurança jurídica para a gestão assinar aditivos contratuais de serviços essenciais contínuos no início do exercício sem risco de descontinuidade."),
    ]
    for i, (tit, lead, cor) in enumerate(sinteses):
        cx = Inches(0.6 + i * 4.1)
        card = s12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.8), Inches(3.9), Inches(5.0))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = tit
        p0.font.bold = True
        p0.font.size = Pt(11)
        p0.font.color.rgb = C_DARK_GREEN
        p1 = tf.add_paragraph()
        p1.text = f"\n{lead}"
        p1.font.bold = True
        p1.font.size = Pt(13)
        p1.font.color.rgb = C_DARK_SLATE
        p2 = tf.add_paragraph()
        p2.text = f"\n{cor}"
        p2.font.size = Pt(10)
        p2.font.color.rgb = C_MUTED_GRAY

    # =========================================================================
    # SLIDE 13: ENCAMINHAMENTO ESTRATÉGICO PARA A GESTÃO
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    add_header(s13, "PLANO DE AÇÃO IMEDIATO", "Encaminhamento Estratégico para a Gestão", "Roteiro de articulação institucional recomendado junto ao Governo Estadual.")

    acoes = [
        ("PASSO 1: NOTA TÉCNICA FORMAL", f"Elaboração de Nota Técnica consolidada demonstrando o piso incompressível de {piso_str} e detalhando os contratos vinculados."),
        ("PASSO 2: PACTUAÇÃO DE CRONOGRAMA", f"Reunião bilateral com a Secretaria-Geral de Governo e Tesouro para pactuar a suplementação formal de {deficit_str} no 2º semestre."),
        ("PASSO 3: GESTÃO E CONTROLE QUINZENAL", "Instituição de Painel de Governança para monitoramento quinzenal do consumo de cota e acompanhamento estrito das supressões pactuadas."),
    ]
    for i, (t_acao, d_acao) in enumerate(acoes):
        ay = Inches(1.8 + i * 1.6)
        card = s13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), ay, Inches(12.1), Inches(1.35))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_EMERALD
        card.line.width = Pt(1.5)
        tf = card.text_frame
        tf.word_wrap = True
        p0 = tf.paragraphs[0]
        p0.text = t_acao
        p0.font.bold = True
        p0.font.size = Pt(13)
        p0.font.color.rgb = C_DARK_GREEN
        p1 = tf.add_paragraph()
        p1.text = d_acao
        p1.font.size = Pt(11)
        p1.font.color.rgb = C_DARK_SLATE

    # Salva arquivos locais
    filename = f"apresentacao_alta_gestao_{'v1' if is_v1 else 'v2'}.pptx"
    out_local = BASE_DIR / filename
    prs.save(str(out_local))
    print(f"Sucesso! Gerado arquivo PowerPoint: {out_local} ({out_local.stat().st_size / 1024:.1f} KB)")

    if BRAIN_DIR.exists():
        out_brain = BRAIN_DIR / filename
        prs.save(str(out_brain))
        print(f"Copiado para diretório brain: {out_brain}")

    return out_local


if __name__ == "__main__":
    build_presentation("v2")
    build_presentation("v1")
