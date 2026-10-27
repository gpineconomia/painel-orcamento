"""Página: Acompanhamento das Contratações 2026."""
from __future__ import annotations

import streamlit as st
import contratacoes_data

contratacoes_data.render_contratacoes_dashboard(key_prefix="page_")
