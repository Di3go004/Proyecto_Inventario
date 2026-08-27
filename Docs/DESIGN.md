---
name: Precision Logic
colors:
  surface: '#fcf8ff'
  surface-dim: '#dbd9e3'
  surface-bright: '#fcf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f2fc'
  surface-container: '#efecf7'
  surface-container-high: '#eae7f1'
  surface-container-highest: '#e4e1eb'
  on-surface: '#1b1b22'
  on-surface-variant: '#464653'
  inverse-surface: '#303037'
  inverse-on-surface: '#f2effa'
  outline: '#767684'
  outline-variant: '#c7c5d5'
  surface-tint: '#4c50c2'
  primary: '#06007c'
  on-primary: '#ffffff'
  primary-container: '#202199'
  on-primary-container: '#9095ff'
  inverse-primary: '#c0c1ff'
  secondary: '#196584'
  on-secondary: '#ffffff'
  secondary-container: '#99dafe'
  on-secondary-container: '#10617f'
  tertiary: '#002431'
  on-tertiary: '#ffffff'
  tertiary-container: '#003b4e'
  on-tertiary-container: '#53a9cd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#04006d'
  on-primary-fixed-variant: '#3336a9'
  secondary-fixed: '#c2e8ff'
  secondary-fixed-dim: '#8ecff2'
  on-secondary-fixed: '#001e2b'
  on-secondary-fixed-variant: '#004d67'
  tertiary-fixed: '#bee9ff'
  tertiary-fixed-dim: '#7ed1f6'
  on-tertiary-fixed: '#001f2a'
  on-tertiary-fixed-variant: '#004d64'
  background: '#fcf8ff'
  on-background: '#1b1b22'
  surface-variant: '#e4e1eb'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-bold:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 20px
  margin: 24px
---

## Brand & Style

The design system is engineered for industrial efficiency and administrative precision. Targeting warehouse managers and logistics coordinators, the interface prioritizes speed of information retrieval over decorative flair. 

The aesthetic is **Corporate / Modern** with a lean toward **Minimalism** to manage high data density. It utilizes a structured grid, high-contrast typography, and a disciplined color application to ensure that critical inventory statuses are immediately visible. The emotional response is one of reliability, order, and control, reflecting the "exactness" inherent in the brand's identity.

## Colors

The palette is anchored by a deep Navy Primary, providing a sense of institutional stability. Light blue accents are reserved for secondary actions and interactive elements to maintain a professional, tech-forward feel.

The color system uses a functional logic for inventory status:
- **Primary/Dark Navy:** Global navigation and structural headers.
- **Success (Green):** Optimal stock levels and completed transactions.
- **Warning (Amber):** Low stock thresholds and pending reviews.
- **Danger (Red):** Out-of-stock critical alerts and system errors.
- **Inactive (Slate Gray):** Retired items or historical data.
- **Active (Secondary Blue):** Loaned items and currently selected states.

## Typography

Inter is chosen for its exceptional legibility in data-heavy environments. To support rapid scanning of inventory lists, this design system utilizes **tabular nump** (tnum) settings for all numeric data, ensuring columns of numbers align perfectly for visual comparison.

Headlines use tighter letter spacing and heavier weights to provide clear section anchoring. Labels are minimized and often presented in uppercase with slight tracking to differentiate them from actionable data.

## Layout & Spacing

This design system employs a **12-column fluid grid** for dashboard views and a **fixed sidebar** model for primary navigation. 

- **Density:** High density is favored to maximize the "above the fold" inventory visibility. Gutters are kept at a crisp 20px.
- **Rhythm:** An 8px linear scale governs all padding and margins.
- **Data Tables:** These are the core of the experience. Use "Comfortable" (16px) vertical cell padding for desktop and "Compact" (8px) for data-intensive administrative tools.
- **Breakpoints:** 
    - Mobile (<768px): Single column, stacked cards replace tables.
    - Tablet (768px - 1024px): 12-column grid, collapsed sidebar (icons only).
    - Desktop (>1024px): 12-column grid, permanent sidebar.

## Elevation & Depth

Visual hierarchy is established through **Tonal Layers** and **Low-contrast outlines** rather than aggressive shadows. This keeps the interface feeling "flat" and industrial.

- **Level 0 (Background):** Neutral Surface (#F8FAFC).
- **Level 1 (Cards/Tables):** Pure White (#FFFFFF) with a 1px solid border (#E2E8F0).
- **Level 2 (Modals/Popovers):** Pure White with a subtle, diffused 12px blur shadow (10% opacity of Primary Blue) to signify temporary focus.
- **Dividers:** 1px solid lines using #E2E8F0 are the primary tool for separating data points within a single surface.

## Shapes

The design system uses **Soft (0.25rem)** roundedness to maintain a precise, geometric feel. This subtle rounding prevents the UI from feeling "sharp" or dated while maintaining the professional rigidity required for a logistics tool.

- **Standard Elements:** (Buttons, Input Fields) 4px radius.
- **Large Elements:** (Cards, Modals) 8px radius.
- **Status Pills:** Fully rounded (pill-shaped) to distinguish them from interactive buttons.

## Components

### Buttons
- **Primary:** Solid Primary Blue with White text. Used for "Add Item" or "Confirm."
- **Secondary:** Outline Primary Blue or Solid Secondary Blue. Used for "Export" or "Filter."
- **Ghost:** No background, Primary Blue text. Used for "Cancel" or "Reset."

### Status Indicators (Chips)
Small, pill-shaped badges with a light tinted background and a high-contrast text color of the same hue (e.g., Success: Light Green BG / Dark Green Text). Use an icon prefix (dot or check) for immediate recognition.

### Input Fields
Strict rectangular forms with a 1px #CBD5E1 border. On focus, the border transitions to Secondary Blue with a 2px outer glow of the same color at 20% opacity.

### Data Tables
The workhorse component. 
- **Headers:** Darkest Navy text, 12px Label-bold font, light gray background (#F1F5F9).
- **Rows:** Alternating zebra stripes for long-list readability.
- **Hover State:** Highlight row with #F1F5F9.

### Inventory Cards
Used for mobile views. Features a clear "Status Bar" on the left edge using the Status Color system to allow users to scan stock health while scrolling.