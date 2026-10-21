"""Página dedicada: Oráculo — Inteligência Orçamentária."""
from __future__ import annotations

import streamlit as st

import oraculo

st.html(
    """<div style="background: linear-gradient(135deg, #064E3B 0%, #0A6B56 60%, #047857 100%);
                border-radius:12px; padding:14px 24px; margin-bottom:1.2rem;
                display:flex; justify-content:space-between; align-items:center; color:#FFFFFF;
                box-shadow: 0 4px 16px rgba(6,78,59,0.22);">
      <div>
        <h2 style="margin:0; font-size:1.55rem; font-weight:800; color:#FFFFFF; letter-spacing:-0.02em;">
          🔮 Oráculo · Inteligência Orçamentária
        </h2>
        <div style="font-size:0.84rem; color:#A7F3D0; margin-top:3px;">
          Consulta unificada em linguagem natural.
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:0.85rem; color:#A7F3D0; font-weight:700;">Secretaria da Economia · GPIN / GELC</div>
        <div style="font-size:0.75rem; color:#D1FAE5; opacity:0.9; margin-top:2px;">● Motor Analítico Multi-Base Ativo</div>
      </div>
    </div>"""
)

oraculo.render_oraculo_chat_ui(key_prefix="page")
