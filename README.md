# 🔥 ThermoLab

A mobile-first Streamlit app for exploring steam/fluid properties and simulating power cycles (Rankine & Brayton), built on **CoolProp** and **Plotly**.

## Features

- **Steam Property Explorer** — look up thermodynamic properties (P, T, h, s, v) for Water, CO₂, Ammonia, R134a, and Air, with live saturation dome / isotherm / isobar charts
- **Power Cycle Lab** — Rankine cycle (ideal, practical, reheat, regenerative) and Brayton cycle analysis with T‑s and P‑h diagrams
- Full unit-conversion system — switch between units (bar/psi/atm, °C/K/°F, kJ/kg, etc.) on any input or chart, live
- Dark / light theme toggle
- Designed mobile-first: collapsible hamburger sidebar, touch-friendly tap targets, responsive 2-column layouts

## Tech stack

- [Streamlit](https://streamlit.io) — UI framework
- [CoolProp](http://coolprop.org) — thermophysical property calculations
- [Plotly](https://plotly.com/python/) — interactive charts
- [pandas](https://pandas.pydata.org) / [NumPy](https://numpy.org) — data handling
