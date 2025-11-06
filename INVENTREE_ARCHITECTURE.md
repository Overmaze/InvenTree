# InvenTree - Comprehensive Architecture & Design Documentation

## Executive Summary

This document provides a complete technical overview of the InvenTree project architecture, design patterns, technologies, module relationships, business rules, and implementation details. It serves as a comprehensive reference for understanding the entire system from backend to frontend, including all modules, integrations, and patterns.

**Project**: InvenTree - Open Source Inventory Management System  
**Status**: Production - Active Development  
**Language**: All code, comments, and concepts in English  
**Architecture**: Django REST Framework (Backend) + React/TypeScript (Frontend)

---

## Development Setup

This section provides quick-start instructions for setting up InvenTree in development mode using Docker Compose.

### Prerequisites

- Docker and Docker Compose installed
- Git repository cloned
- Sufficient disk space (recommended: 5GB+)

### Quick Start - Development Environment

The development environment uses Docker Compose to orchestrate all services. Follow these steps to get started:

#### Step 1: Install Dependencies

Install all required Python packages and plugins:

```bash
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke install
```

**What this does**:
- Installs all Python dependencies from `requirements.txt`
- Installs plugins from `plugins.txt`
- Sets up the Python environment
- Compiles license information

**Expected output**: 
- Success message: "Dependency installation complete"
- All packages installed in the container

#### Step 2: Setup Test Environment

Initialize the database with migrations and load demo data:

```bash
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke dev.setup-test
```

**What this does**:
- Runs database migrations
- Downloads and loads demo dataset from GitHub
- Imports sample data (parts, orders, stock items, etc.)
- Copies media files
- Sets up a complete development environment with realistic data

**Expected output**:
- Database migrations completed
- Demo dataset cloned and imported
- Media files copied
- Test environment ready

**Note**: This command will:
- Clone the `inventree-demo-dataset` repository
- Import all data from `inventree_data.json`
- Copy media files to the media directory
- This may take a few minutes depending on your internet connection

#### Step 3: Create Superuser Account

Create an administrator account to access the web interface:

```bash
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke superuser
```

**What this does**:
- Launches interactive Django `createsuperuser` command
- Prompts for username, email, and password
- Creates the admin account in the database

**Interactive prompts**:
```
Username: admin
Email address: admin@example.com
Password: ********
Password (again): ********
Superuser created successfully.
```

### Starting the Development Server

After completing the setup, start the development servers:

```bash
# Start all services (backend, frontend, worker, database, redis)
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml up

# Or run in detached mode
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml up -d
```

**Access the application**:
- **Frontend UI**: http://localhost:5173 (Main application interface)
  - Example: http://localhost:5173/web/purchasing/index/suppliers
- **Backend API**: http://localhost:8000/api/ (REST API endpoints)
- **API Documentation**: http://localhost:8000/api/docs/ (API schema documentation)

**Note**: The frontend (port 5173) is the primary user interface. The backend (port 8000) serves only the REST API - there is no admin panel UI at the backend URL.

### Development Workflow

**Common Development Tasks**:

```bash
# Run Django shell
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke dev.shell

# Run tests
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke dev.test

# Run migrations
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke migrate

# Update system (after pulling new code)
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke update

# Start background worker
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke worker
```

### Troubleshooting

**Issue: Dependencies not installing**
- Check Docker is running: `docker ps`
- Check container logs: `docker compose logs inventree-dev-server`
- Verify network connectivity

**Issue: Database connection errors**
- Ensure database container is running: `docker compose ps`
- Check database logs: `docker compose logs inventree-db`
- Verify environment variables in `contrib/container/docker.dev.env`

**Issue: Demo data not loading**
- Check internet connection (clones from GitHub)
- Verify sufficient disk space
- Check logs for specific errors: `docker compose logs inventree-dev-server`

**Issue: Port conflicts**
- Backend default: 8000 (change in `dev-docker-compose.yml`)
- Frontend default: 3000 (change in `dev-docker-compose.yml`)
- Database default: 5432 (PostgreSQL)

### Additional Setup Options

**Skip demo data** (clean database):
```bash
# Just run migrations without demo data
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke migrate
```

**Setup with development tools**:
```bash
# Install development dependencies (pre-commit, etc.)
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke dev.setup-dev
```

**Custom test dataset path**:
```bash
# Use a different dataset path
docker compose --project-directory . -f contrib/container/dev-docker-compose.yml run inventree-dev-server invoke dev.setup-test --path /path/to/dataset
```

### Environment Variables

Key environment variables for development (in `contrib/container/docker.dev.env`):

- `INVENTREE_DOCKER=1`: Enables Docker-specific behavior
- `DEBUG=True`: Enables Django debug mode
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Django secret key (auto-generated)

### Next Steps

After setup:
1. ✅ Access the web interface at http://localhost:5173
2. ✅ Login with your superuser credentials
3. ✅ Explore the demo data (parts, orders, stock items, suppliers, etc.)
   - Example navigation: http://localhost:5173/web/purchasing/index/suppliers
4. ✅ Review the API documentation at http://localhost:8000/api/docs/
5. ✅ Start developing following the patterns in this document

For more detailed information about:
- **Architecture**: See Section 2 - System Architecture
- **Modules**: See Section 6 - Module Details
- **API**: See Section 7 - API Architecture
- **Plugins**: See Section 8 - Plugin System
- **Development**: See Section 16.8 - Invoke Tasks

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Overview](#1-project-overview)
3. [System Architecture](#2-system-architecture)
4. [Backend Architecture](#3-backend-architecture)
5. [Frontend Architecture](#4-frontend-architecture)
6. [Core Models & Mixins](#5-core-models--mixins)
7. [Module Details](#6-module-details)
8. [API Architecture](#7-api-architecture)
9. [Plugin System](#8-plugin-system)
10. [State Management & Status Codes](#9-state-management--status-codes)
11. [Permissions & Security](#10-permissions--security)
12. [Data Flow & Relationships](#11-data-flow--relationships)
13. [Background Tasks & Events](#12-background-tasks--events)
14. [Testing Strategy](#13-testing-strategy)
15. [Deployment & Configuration](#14-deployment--configuration)
16. [Design Patterns](#15-design-patterns)
17. [Key Concepts Explained](#16-key-concepts-explained)

---

## 1. Project Overview

### 1.1 Purpose

InvenTree is an open-source Inventory Management System designed for:
- **Low-level stock control** - Track physical stock items with precise quantities
- **Part tracking** - Manage parts catalog with hierarchical categories
- **Order management** - Handle purchase orders, sales orders, and return orders
- **Manufacturing** - Support build orders and production workflows
- **Company management** - Track suppliers, customers, and manufacturers
- **Integration** - REST API for external applications
- **Extensibility** - Plugin system for custom functionality

### 1.2 Key Features

- **Stock Management**: Track stock items by location, quantity, batch, serial numbers
- **Part Catalog**: Hierarchical part categories with BOM (Bill of Materials) support
- **Order Processing**: Purchase, sales, and return order workflows
- **Manufacturing**: Build orders with stock allocation and consumption
- **Company Relations**: Supplier, customer, and manufacturer management
- **Reporting**: Generate reports and labels
- **Barcode Support**: QR codes and external barcode integration
- **Notifications**: Event-driven notification system
- **Multi-tenant**: Support for multiple companies/owners
- **Internationalization**: Multi-language support (40+ languages)

### 1.3 Technology Stack

**Backend**:
- Python 3.11+
- Django 5.x (Web framework)
- Django REST Framework (API)
- PostgreSQL/MySQL/SQLite (Database)
- Redis (Caching & task queue)
- Django Q2 (Background tasks)
- Django Allauth (Authentication & SSO)
- MPTT (Modified Preorder Tree Traversal)

**Frontend**:
- React 19+
- TypeScript
- Mantine UI (Component library)
- TanStack Query (Data fetching)
- React Router (Routing)
- Zustand (State management)
- Lingui (Internationalization)
- Vite (Build tool)

**DevOps**:
- Docker (Containerization)
- Gunicorn (WSGI server)
- Nginx/Caddy (Reverse proxy)
- GitHub Actions (CI/CD)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Client Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Web Browser  │  │ Mobile App   │  │  API Client  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                        │
                        │ HTTP/HTTPS
                        │
┌─────────────────────────────────────────────────────────┐
│                  Frontend Layer (React)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Pages      │  │   Tables     │  │   Forms      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Hooks      │  │  Components  │  │   Contexts   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                        │
                        │ REST API
                        │
┌─────────────────────────────────────────────────────────┐
│              Backend Layer (Django/DRF)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Views      │  │ Serializers  │  │  Models      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Filters    │  │  Permissions │  │   Plugins    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
│  PostgreSQL  │ │    Redis    │ │  Storage   │
│   (Primary)  │ │   (Cache)   │ │  (Media)   │
└──────────────┘ └─────────────┘ └────────────┘
```

### 2.2 Request Flow

1. **User Request**: User interacts with React frontend
2. **API Call**: Frontend makes API request via TanStack Query
3. **Middleware**: Django middleware processes request (auth, CORS, etc.)
4. **View**: DRF view handles request
5. **Permission Check**: Role-based permission validation
6. **Serializer**: Data validation and transformation
7. **Model**: Database query and business logic
8. **Response**: JSON response sent back to frontend
9. **State Update**: Frontend updates React state via TanStack Query

### 2.3 Directory Structure

```
InvenTree/
├── src/
│   ├── backend/
│   │   └── InvenTree/
│   │       ├── InvenTree/          # Core app
│   │       ├── build/              # Manufacturing module
│   │       ├── common/             # Shared utilities
│   │       ├── company/            # Company management
│   │       ├── order/              # Order management
│   │       ├── part/               # Parts catalog
│   │       ├── plugin/             # Plugin system
│   │       ├── report/             # Reporting
│   │       ├── stock/              # Stock management
│   │       ├── users/              # User management
│   │       ├── generic/            # Generic state management
│   │       ├── machine/            # Machine integration
│   │       ├── importer/           # Data import
│   │       └── data_exporter/      # Data export
│   └── frontend/
│       └── src/
│           ├── pages/              # Page components
│           ├── tables/             # Data tables
│           ├── forms/               # Form definitions
│           ├── components/          # Reusable components
│           ├── hooks/               # Custom hooks
│           ├── states/              # State management
│           ├── lib/                 # Library code
│           └── router.tsx           # Routing
├── docs/                            # Documentation
├── contrib/                         # Contrib scripts
└── data/                           # Runtime data
```

---

## 3. Backend Architecture

### 3.1 Django App Structure

Each Django app follows a consistent structure:

```
app_name/
├── __init__.py
├── apps.py                 # AppConfig class
├── models.py               # Database models
├── serializers.py         # DRF serializers
├── api.py                 # API views and URLs
├── admin.py               # Django admin registration
├── filters.py             # Query filters (optional)
├── status_codes.py        # Status code definitions (if applicable)
├── events.py              # Event definitions (if applicable)
├── tasks.py               # Background tasks (if applicable)
├── validators.py          # Custom validators (if applicable)
├── migrations/            # Database migrations
├── fixtures/              # Test fixtures (YAML format)
└── tests.py / test_*.py   # Unit tests
```

### 3.2 Core Modules

#### 3.2.1 InvenTree Core (`InvenTree/`)

**Purpose**: Core framework and shared functionality

**Key Components**:
- **Models** (`models.py`): Base mixins and model classes
- **Settings** (`settings.py`): Django configuration
- **URLs** (`urls.py`): Top-level URL routing
- **Middleware**: Custom middleware for auth, caching, etc.
- **Helpers**: Utility functions for formatting, conversion, etc.

**Key Mixins** (from `models.py`):
- `InvenTreeModel`: Base model class with plugin validation
- `MetadataMixin`: JSON metadata field for plugins
- `InvenTreeAttachmentMixin`: File attachment support
- `InvenTreeBarcodeMixin`: Barcode/QR code support
- `InvenTreeNotesMixin`: Notes field with markdown support
- `ReferenceIndexingMixin`: Auto-incrementing reference numbers

#### 3.2.2 Part Module (`part/`)

**Purpose**: Parts catalog management

**Key Models**:
- `Part`: Main part model (hierarchical via MPTT)
- `PartCategory`: Category tree for organizing parts
- `PartParameter`: Custom parameters for parts
- `PartTestTemplate`: Test templates for parts
- `BomItem`: Bill of Materials items
- `PartAttachment`: Attachments for parts

**Business Rules**:
- Parts can be trackable (serial numbers) or non-trackable (quantities)
- Parts can be assembly (has BOM) or component
- Parts can be salable (can be sold) or purchasable
- Parts have a category tree structure
- Parts can have custom parameters and test templates

**Relationships**:
- `Part` → `PartCategory` (TreeForeignKey)
- `Part` → `BomItem` (One-to-many, self-referential)
- `Part` → `StockItem` (One-to-many)
- `Part` → `SupplierPart` (One-to-many)
- `Part` → `ManufacturerPart` (One-to-many)

#### 3.2.3 Stock Module (`stock/`)

**Purpose**: Physical stock item tracking

**Key Models**:
- `StockItem`: Individual stock items
- `StockLocation`: Hierarchical location tree
- `StockItemTracking`: History/audit trail
- `StockItemAttachment`: Attachments

**Business Rules**:
- Stock items have quantities (decimal, 15 digits, 5 decimals)
- Stock items can be tracked by serial number or batch
- Stock items belong to a location (hierarchical)
- Stock items can be allocated to builds, sales orders, or loans
- Stock items track expiry dates
- Stock items can be split or merged
- Stock items maintain a complete history via tracking entries

**Status Codes**:
- `OK`: Available stock
- `ATTENTION`: Needs attention
- `DAMAGED`: Damaged item
- `DESTROYED`: Destroyed item
- `LOST`: Lost item
- `QUARANTINED`: Quarantined item
- `REJECTED`: Rejected item
- `RETURNED`: Returned from customer

**Relationships**:
- `StockItem` → `Part` (Foreign key)
- `StockItem` → `StockLocation` (TreeForeignKey)
- `StockItem` → `PurchaseOrder` (Optional, source)
- `StockItem` → `SalesOrder` (Optional, destination)
- `StockItem` → `Build` (Optional, source or consumed_by)
- `StockItem` → `StockItem` (Parent-child relationship)

#### 3.2.4 Order Module (`order/`)

**Purpose**: Purchase, sales, and return order management

**Key Models**:
- `Order`: Base order class (abstract)
- `PurchaseOrder`: Purchase orders
- `SalesOrder`: Sales orders
- `ReturnOrder`: Return orders
- `PurchaseOrderLineItem`: Line items for purchase orders
- `SalesOrderLineItem`: Line items for sales orders
- `ReturnOrderLineItem`: Line items for return orders
- `PurchaseOrderAllocation`: Stock allocation to purchase orders
- `SalesOrderAllocation`: Stock allocation to sales orders
- `ReturnOrderAllocation`: Stock allocation for returns

**Business Rules**:
- Orders have reference numbers (auto-generated, configurable pattern)
- Orders have status codes (PENDING, APPROVED, COMPLETE, etc.)
- Orders track line items with quantities
- Orders can be allocated to stock items
- Orders support extra line items (non-part items)
- Orders track shipping addresses and contacts
- Orders can be linked to projects

**Order Status Flow**:
```
PurchaseOrder:
PENDING → APPROVED → PLACED → RECEIVED → COMPLETE
                ↓
            CANCELLED

SalesOrder:
PENDING → IN_PROGRESS → SHIPPED → DELIVERED → COMPLETE
            ↓
        CANCELLED

ReturnOrder:
PENDING → IN_PROGRESS → COMPLETE
```

**Relationships**:
- `PurchaseOrder` → `Company` (supplier)
- `PurchaseOrder` → `StockItem` (via allocations)
- `SalesOrder` → `Company` (customer)
- `SalesOrder` → `StockItem` (via allocations)
- `SalesOrder` → `Build` (for manufactured items)
- `ReturnOrder` → `SalesOrder` (source order)

#### 3.2.5 Build Module (`build/`)

**Purpose**: Manufacturing and production orders

**Key Models**:
- `Build`: Build order
- `BuildLine`: BOM line items for a build
- `BuildItem`: Stock allocation to build lines
- `BuildAttachment`: Attachments

**Business Rules**:
- Builds create stock items from parts with BOM
- Builds consume stock items from BOM lines
- Builds track allocated vs consumed quantities
- Builds can be internal or external
- Builds can be linked to sales orders
- Builds track output stock location
- Builds maintain completion status

**Build Status Flow**:
```
PENDING → PRODUCTION → COMPLETE
            ↓
        CANCELLED
```

**Relationships**:
- `Build` → `Part` (what to build)
- `Build` → `SalesOrder` (optional, linked order)
- `Build` → `StockLocation` (source and destination)
- `Build` → `BuildLine` → `BomItem`
- `BuildItem` → `StockItem` (allocated stock)
- `Build` → `StockItem` (output items)

#### 3.2.6 Company Module (`company/`)

**Purpose**: Company, supplier, customer, and manufacturer management

**Key Models**:
- `Company`: Base company model
- `SupplierPart`: Parts available from suppliers
- `ManufacturerPart`: Parts manufactured by manufacturers
- `Contact`: Contact persons
- `Address`: Shipping addresses
- `SupplierPriceBreak`: Pricing for supplier parts

**Business Rules**:
- Companies can be suppliers, customers, or manufacturers
- Companies have contacts and addresses
- Supplier parts link to internal parts
- Supplier parts have pricing with quantity breaks
- Manufacturer parts link to internal parts

**Relationships**:
- `Company` → `SupplierPart` → `Part`
- `Company` → `ManufacturerPart` → `Part`
- `Company` → `Contact` (One-to-many)
- `Company` → `Address` (One-to-many)
- `Company` → `PurchaseOrder` (as supplier)
- `Company` → `SalesOrder` (as customer)

#### 3.2.7 Common Module (`common/`)

**Purpose**: Shared utilities and settings

**Key Components**:
- `ProjectCode`: Project code tracking
- `InvenTreeSetting`: System settings
- `NotificationMessage`: User notifications
- `Currency`: Currency management
- `WebhookEndpoint`: Webhook configuration

**Settings System**:
- Settings are defined in `common/setting/`
- Settings can be configured via `config.yaml`
- Settings support validation and default values
- Settings are cached for performance

#### 3.2.8 Users Module (`users/`)

**Purpose**: User management and permissions

**Key Models**:
- `Owner`: Represents users or groups (unified ownership)
- Permission system via Django's auth framework
- Role-based access control (RBAC)

**Permission System**:
- Rulesets defined in `ruleset.py`
- Each model has a ruleset (e.g., `part`, `stock`, `order`)
- Permissions: `view`, `add`, `change`, `delete`
- Permissions checked via `RolePermission` class

**Rulesets**:
- `PART`: Part management
- `STOCK`: Stock management
- `STOCK_LOCATION`: Location management
- `BUILD`: Build order management
- `PURCHASE_ORDER`: Purchase order management
- `SALES_ORDER`: Sales order management
- `RETURN_ORDER`: Return order management
- `COMPANY`: Company management

#### 3.2.9 Report Module (`report/`)

**Purpose**: Report and label generation

**Key Components**:
- Report templates (Jinja2/Liquid templates)
- Label templates
- Report generation via WeasyPrint (PDF)
- Report context mixins for models

**Report Types**:
- Part reports
- Stock item reports
- Order reports (Purchase, Sales, Return)
- Build reports
- Label reports (barcode labels)

#### 3.2.10 Plugin Module (`plugin/`)

**Purpose**: Plugin system for extensibility

**Architecture**:
- Plugin registry (`registry.py`)
- Plugin base class (`InvenTreePlugin`)
- Mixin system for plugin capabilities
- Event system for plugin hooks

**Plugin Types** (Mixins):
- `ActionMixin`: Add action buttons
- `EventMixin`: Listen to events
- `NavigationMixin`: Add navigation items
- `PanelMixin`: Add UI panels
- `ValidationMixin`: Validate model instances
- `StateTransitionMixin`: Handle state transitions
- `SettingsMixin`: Add plugin settings
- `URLMixin`: Add URL routes
- `APIMixin`: Add API endpoints

**Plugin Loading**:
1. Plugins discovered from `plugins/` directory or installed packages
2. Plugin configuration loaded from database
3. Plugins initialized in order
4. Mixins registered
5. Plugin ready for use

#### 3.2.11 Generic Module (`generic/`)

**Purpose**: Generic state management and utilities

**Key Components**:
- `StatusCode`: Base class for status codes
- `StatusCodeMixin`: Model mixin for status codes
- `StateTransitionMixin`: State transition handling
- `TransitionMethod`: Decorator for state transitions

**Status Code System**:
- Status codes defined as IntEnum subclasses
- Each status has: value (int), label (string), color (enum)
- Custom status codes stored in database
- Status groups for filtering

---

## 4. Frontend Architecture

### 4.1 React Structure

**Framework**: React 19 with TypeScript

**Key Libraries**:
- **Mantine UI**: Component library
- **TanStack Query**: Data fetching and caching
- **React Router**: Client-side routing
- **Zustand**: State management
- **Lingui**: Internationalization
- **Axios**: HTTP client

### 4.2 Component Architecture

```
src/
├── pages/              # Page-level components
│   ├── Index/          # Home page
│   ├── part/           # Part pages
│   ├── stock/           # Stock pages
│   ├── purchasing/      # Purchase order pages
│   ├── sales/           # Sales order pages
│   ├── build/          # Build order pages
│   ├── company/        # Company pages
│   └── Auth/           # Authentication pages
├── tables/             # Data table components
│   ├── part/           # Part tables
│   ├── stock/          # Stock tables
│   ├── purchasing/     # Purchase order tables
│   └── sales/          # Sales order tables
├── forms/              # Form field definitions
│   ├── PartForms.tsx
│   ├── StockForms.tsx
│   ├── PurchaseOrderForms.tsx
│   └── ...
├── components/         # Reusable components
│   ├── forms/          # Form components
│   ├── tables/         # Table components
│   ├── details/        # Detail view components
│   ├── modals/         # Modal dialogs
│   └── ...
├── hooks/              # Custom React hooks
│   ├── UseInstance.tsx # Fetch single instance
│   ├── UseTable.tsx    # Table state management
│   ├── UseForm.tsx     # Form handling
│   └── ...
├── states/              # Zustand state stores
│   ├── UserState.tsx
│   ├── LocalState.tsx
│   └── ...
└── lib/                 # Library code
    ├── enums/           # TypeScript enums
    │   ├── ApiEndpoints.tsx
    │   ├── ModelType.tsx
    │   └── ...
    └── functions/       # Utility functions
```

### 4.3 Data Fetching Pattern

**TanStack Query Integration**:

```typescript
// Hook for fetching single instance
const { instance, instanceQuery } = useInstance({
  endpoint: ApiEndpoints.part_detail,
  pk: id
});

// Hook for table data
const table = useTable('part');
const { data, isLoading } = useQuery({
  queryKey: ['tabledata', url, tableState.page, ...],
  queryFn: fetchTableData
});
```

**API Endpoints**:
- Defined in `lib/enums/ApiEndpoints.tsx`
- Snake_case format: `part_detail`, `stock_item_list`
- URL construction via `apiUrl()` function

### 4.4 Routing

**React Router Setup**:
```typescript
// Lazy-loaded routes
export const PartDetail = Loadable(
  lazy(() => import('./pages/part/PartDetail'))
);

// Route definition
<Route path="/part/:id/" element={<PartDetail />} />
```

**Route Structure**:
- `/`: Home
- `/part/:id/`: Part detail
- `/stock/:id/`: Stock item detail
- `/purchasing/order/:id/`: Purchase order detail
- `/sales/order/:id/`: Sales order detail
- `/build/:id/`: Build order detail
- `/company/:id/`: Company detail

### 4.5 State Management

**Zustand Stores**:
- `UserState`: Current user information
- `LocalState`: Local storage and preferences
- `ModalState`: Modal dialog state
- `TableState`: Table state (persisted)

### 4.6 Form Handling

**ApiForm Component**:
- Dynamic form generation from API field definitions
- Field types: string, number, date, related_field, choice, etc.
- Validation via API
- Submission via POST/PATCH

**Form Definition Pattern**:
```typescript
export const partFields: ApiFormFieldSet = {
  name: {
    type: 'string',
    required: true,
    label: t`Part Name`
  },
  category: {
    type: 'related_field',
    model_field: 'category',
    api_query: {
      endpoint: ApiEndpoints.category_list
    }
  }
};
```

---

## 5. Core Models & Mixins

### 5.1 Base Model Classes

#### InvenTreeModel
**Location**: `InvenTree/models.py`

**Purpose**: Base class for all InvenTree models

**Mixins**:
- `PluginValidationMixin`: Plugin validation support
- `DiffMixin`: Track field changes

**Usage**:
```python
class MyModel(InvenTreeModel):
    name = models.CharField(max_length=100)
```

#### InvenTreeMetadataModel
**Purpose**: Base model with metadata field

**Mixins**:
- `MetadataMixin`: JSON metadata field
- `InvenTreeModel`: Base functionality

**Usage**:
```python
class MyModel(InvenTreeMetadataModel):
    name = models.CharField(max_length=100)
    
    # Has metadata field automatically
    # model.metadata = {'custom_key': 'value'}
```

### 5.2 Core Mixins

#### PluginValidationMixin
**Purpose**: Allow plugins to validate model instances

**Methods**:
- `run_plugin_validation()`: Run plugin validators
- `full_clean()`: Override to include plugin validation
- `save()`: Override to include plugin validation
- `delete()`: Override to include plugin validation

**Usage**:
```python
class MyModel(PluginValidationMixin, models.Model):
    # Plugins can validate this model
    pass
```

#### MetadataMixin
**Purpose**: Add JSON metadata field for plugins

**Fields**:
- `metadata`: JSONField for plugin data

**Methods**:
- `get_metadata(key, backup_value)`: Get metadata value
- `set_metadata(key, value)`: Set metadata value

#### InvenTreeAttachmentMixin
**Purpose**: File attachment support

**Features**:
- Automatic attachment handling
- Attachment API endpoints
- Attachment UI components

#### InvenTreeBarcodeMixin
**Purpose**: Barcode and QR code support

**Fields**:
- `barcode_data`: Raw barcode data
- `barcode_hash`: Hash for matching

**Methods**:
- `barcode_model_type_code()`: Must be implemented
- `format_barcode()`: Format QR code string

#### InvenTreeNotesMixin
**Purpose**: Notes field with markdown support

**Fields**:
- `notes`: TextField for notes

**Features**:
- Markdown rendering
- Rich text editor support

#### ReferenceIndexingMixin
**Purpose**: Auto-incrementing reference numbers

**Fields**:
- `reference`: CharField (auto-generated)
- `reference_int`: BigIntegerField (for sorting)

**Methods**:
- `generate_next_reference()`: Generate next reference
- `validate_reference_field()`: Validate reference pattern

**Configuration**:
- Reference pattern via settings: `PART_REFERENCE_PATTERN`
- Pattern format: `PART-{ref:04d}`

### 5.3 Status Code System

#### StatusCodeMixin
**Purpose**: Status code management for models

**Requirements**:
- Model must have `STATUS_CLASS` attribute
- Model must have `status` field (InvenTreeCustomStatusModelField)
- Optional: `status_custom_key` field for custom statuses

**Methods**:
- `get_status()`: Get current status code
- `set_status(status)`: Set status code
- `compare_status(status)`: Compare status

**Example**:
```python
class MyModel(StatusCodeMixin, models.Model):
    STATUS_CLASS = MyStatus
    
    status = InvenTreeCustomStatusModelField(
        default=MyStatus.PENDING.value
    )

# Usage
instance.set_status(MyStatus.COMPLETE.value)
```

#### StateTransitionMixin
**Purpose**: Handle state transitions with plugin hooks

**Usage**:
```python
class MyModel(StateTransitionMixin, models.Model):
    @TransitionMethod(
        source=[MyStatus.PENDING],
        target=MyStatus.COMPLETE,
        method_name='complete'
    )
    def complete(self, user=None):
        self.set_status(MyStatus.COMPLETE)
        self.save()
```

**Features**:
- Plugin hooks for state transitions
- Validation before transitions
- Automatic tracking entries

---

## 6. Module Details

### 6.1 Part Module

#### Part Model
**File**: `part/models.py`

**Key Fields**:
- `name`: Part name
- `description`: Part description
- `category`: TreeForeignKey to PartCategory
- `trackable`: Boolean (serial number tracking)
- `assembly`: Boolean (has BOM)
- `purchasable`: Boolean (can be purchased)
- `salable`: Boolean (can be sold)
- `component`: Boolean (is a component)
- `virtual`: Boolean (not physical)
- `active`: Boolean (is active)

**Business Rules**:
- Parts must have a category
- Trackable parts use serial numbers
- Assembly parts have BOM
- Only salable parts can be in sales orders
- Only purchasable parts can be in purchase orders

**Relationships**:
```python
Part
├── category (TreeForeignKey → PartCategory)
├── bom_items (reverse → BomItem)
├── stock_items (reverse → StockItem)
├── supplier_parts (reverse → SupplierPart)
└── manufacturer_parts (reverse → ManufacturerPart)
```

#### BomItem Model
**Purpose**: Bill of Materials items

**Key Fields**:
- `parent_part`: Part that uses this item
- `part`: Part being used
- `quantity`: Quantity required
- `substitute_part`: Optional substitute

**Business Rules**:
- BomItems form a tree (parent → child)
- Quantities are decimal (15 digits, 5 decimals)
- Substitute parts can be used in builds

### 6.2 Stock Module

#### StockItem Model
**File**: `stock/models.py`

**Key Fields**:
- `part`: ForeignKey to Part
- `location`: TreeForeignKey to StockLocation
- `quantity`: Decimal (15,5)
- `serial`: CharField (for trackable parts)
- `batch`: CharField (batch tracking)
- `status`: StatusCode field
- `purchase_order`: Optional source purchase order
- `sales_order`: Optional destination sales order
- `build`: Optional source build
- `consumed_by`: Optional build that consumed this item

**Business Rules**:
- Trackable parts: quantity = 1, serial required
- Non-trackable parts: quantity > 0, no serial
- Stock items can be split (parent → children)
- Stock items track allocation (builds, sales, loans)
- Stock items maintain history via tracking entries

**Stock Allocation**:
```python
# Check available quantity
available = item.quantity - (
    item.build_allocation_count() +
    item.sales_order_allocation_count() +
    item.loan_allocation_count()
)
```

#### StockLocation Model
**Purpose**: Hierarchical location tree

**Key Fields**:
- `name`: Location name
- `parent`: TreeForeignKey (self-referential)
- `description`: Location description

**Business Rules**:
- Locations form a tree structure
- Stock items belong to one location
- Locations can have sub-locations

### 6.3 Order Module

#### PurchaseOrder Model
**File**: `order/models.py`

**Key Fields**:
- `reference`: Auto-generated reference
- `supplier`: ForeignKey to Company
- `status`: StatusCode field
- `order_date`: Date
- `target_date`: Target delivery date
- `complete_date`: Completion date

**Business Rules**:
- Purchase orders create stock items when received
- Purchase orders track received quantities
- Purchase orders can be cancelled

#### SalesOrder Model
**Key Fields**:
- `reference`: Auto-generated reference
- `customer`: ForeignKey to Company
- `status`: StatusCode field
- `shipment_date`: Date shipped
- `delivery_date`: Date delivered

**Business Rules**:
- Sales orders allocate stock items
- Sales orders can be linked to builds
- Sales orders track shipped quantities

#### SalesOrderAllocation Model
**Purpose**: Allocate stock items to sales orders

**Key Fields**:
- `line`: ForeignKey to SalesOrderLineItem
- `item`: ForeignKey to StockItem
- `quantity`: Allocated quantity

**Business Rules**:
- Allocations reserve stock
- Stock items show as "allocated" when allocated
- Allocations can be completed (shipped)

### 6.4 Build Module

#### Build Model
**File**: `build/models.py`

**Key Fields**:
- `reference`: Auto-generated reference
- `part`: Part to build
- `quantity`: Quantity to build
- `status`: StatusCode field
- `sales_order`: Optional linked sales order
- `take_from`: Source location
- `destination`: Output location

**Business Rules**:
- Builds consume stock from BOM
- Builds create output stock items
- Builds track allocated vs consumed quantities
- Builds can be internal or external

#### BuildLine Model
**Purpose**: BOM line items for a build

**Key Fields**:
- `build`: ForeignKey to Build
- `bom_item`: ForeignKey to BomItem
- `quantity`: Required quantity
- `allocated`: Allocated quantity
- `consumed`: Consumed quantity

#### BuildItem Model
**Purpose**: Stock allocation to build lines

**Key Fields**:
- `build_line`: ForeignKey to BuildLine
- `stock_item`: ForeignKey to StockItem
- `quantity`: Allocated quantity

**Business Rules**:
- BuildItems allocate stock to builds
- Stock is consumed when build completes
- Trackable parts are installed into output

---

## 7. API Architecture

### 7.1 API Structure

**Base URL**: `/api/`

**URL Patterns**:
```python
# In urls.py
apipatterns = [
    path('part/', include(part.api.part_api_urls)),
    path('stock/', include(stock.api.stock_api_urls)),
    path('order/', include(order.api.order_api_urls)),
    path('build/', include(build.api.build_api_urls)),
    path('company/', include(company.api.company_api_urls)),
    # ...
]
```

### 7.2 API View Classes

#### ListCreateAPI
**Purpose**: List and create endpoints

**Features**:
- GET: List with pagination, filtering, searching
- POST: Create new instance

**Example**:
```python
class PartList(ListCreateAPI):
    queryset = Part.objects.all()
    serializer_class = PartSerializer
    filterset_class = PartFilter
    role_required = 'part.view'
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created']
```

#### RetrieveUpdateDestroyAPI
**Purpose**: Detail, update, delete endpoints

**Features**:
- GET: Retrieve single instance
- PATCH: Partial update
- PUT: Full update
- DELETE: Delete instance

**Example**:
```python
class PartDetail(RetrieveUpdateDestroyAPI):
    queryset = Part.objects.all()
    serializer_class = PartSerializer
    role_required = 'part.view'
```

### 7.3 Serializers

#### Base Serializer Pattern
```python
class PartSerializer(
    InvenTreeModelSerializer,
    NotesFieldMixin,
    MetadataSerializerMixin
):
    class Meta:
        model = Part
        fields = [
            'pk',
            'name',
            'description',
            'category',
            'category_detail',
            'notes',
            'metadata',
            # ...
        ]
        read_only_fields = ['pk']
    
    category_detail = PartCategorySerializer(
        source='category',
        read_only=True
    )
```

**Serializer Mixins**:
- `NotesFieldMixin`: Notes field support
- `MetadataSerializerMixin`: Metadata field support
- `FilterableSerializerMixin`: Filtering support
- `DataImportExportSerializerMixin`: Import/export support

### 7.4 Filtering & Search

**Django Filter Integration**:
```python
class PartFilter(rest_filters.FilterSet):
    name = rest_filters.CharFilter(lookup_expr='icontains')
    category = rest_filters.ModelChoiceFilter(
        queryset=PartCategory.objects.all()
    )
    
    class Meta:
        model = Part
        fields = ['name', 'category', 'active']
```

**Search Fields**:
```python
search_fields = [
    'name',
    'description',
    'IPN',  # Internal Part Number
    'category__name'
]
```

**Ordering**:
```python
ordering_fields = ['name', 'created', 'updated']
ordering = ['-created']  # Default ordering
```

### 7.5 Permissions

**RolePermission Class**:
```python
class PartList(ListCreateAPI):
    role_required = 'part.view'  # For GET
    # Automatically uses 'part.add' for POST
```

**Permission Checks**:
- `view`: Read access
- `add`: Create access
- `change`: Update access
- `delete`: Delete access

---

## 8. Plugin System

### 8.1 Plugin Architecture

**Registry System**:
- `PluginsRegistry`: Central plugin registry
- Plugin discovery from `plugins/` directory
- Plugin configuration in database (`PluginConfig` model)
- Plugin initialization on startup

**Plugin Base Class**:
```python
class InvenTreePlugin(MixinBase, MetaBase):
    """Base class for all InvenTree plugins."""
    
    NAME: str  # Plugin name
    SLUG: str  # Plugin slug (unique)
    TITLE: str  # Human-readable title
    DESCRIPTION: str  # Plugin description
    VERSION: str  # Version string
    AUTHOR: str  # Author name
    
    def __init__(self):
        # Plugin initialization
        pass
```

### 8.2 Plugin Mixins

#### ActionMixin
**Purpose**: Add action buttons to UI

**Methods**:
- `get_action_items()`: Return action buttons

#### EventMixin
**Purpose**: Listen to system events

**Methods**:
- `process_event(event, *args, **kwargs)`: Handle event

**Events**:
- `part.created`, `part.updated`, `part.deleted`
- `stock.created`, `stock.updated`
- `order.created`, `order.updated`
- Custom events

#### NavigationMixin
**Purpose**: Add navigation items

**Methods**:
- `get_navigation_items()`: Return navigation items

#### PanelMixin
**Purpose**: Add UI panels to detail pages

**Methods**:
- `get_panels()`: Return panel definitions

#### ValidationMixin
**Purpose**: Validate model instances

**Methods**:
- `validate_model_instance(instance, deltas)`: Validate
- `validate_model_deletion(instance)`: Validate deletion

#### StateTransitionMixin
**Purpose**: Handle state transitions

**Methods**:
- `on_state_transition(instance, transition)`: Handle transition

### 8.3 Plugin Events

**Event System**:
```python
from plugin.events import trigger_event

# Trigger event
trigger_event('part.created', part_pk=part.pk)

# Listen to event (in plugin)
class MyPlugin(EventMixin, InvenTreePlugin):
    def process_event(self, event, *args, **kwargs):
        if event == 'part.created':
            part_pk = kwargs.get('part_pk')
            # Handle event
```

### 8.4 Plugin Configuration

**Settings**:
```python
class MyPlugin(SettingsMixin, InvenTreePlugin):
    SETTINGS = {
        'API_KEY': {
            'name': 'API Key',
            'description': 'API key for external service',
            'default': '',
            'validator': str
        }
    }
```

**Access Settings**:
```python
api_key = self.get_setting('API_KEY')
```

---

## 9. State Management & Status Codes

### 9.1 Status Code System

#### StatusCode Base Class
**File**: `generic/states/states.py`

**Definition**:
```python
class MyStatus(StatusCode):
    PENDING = 10, _('Pending'), ColorEnum.info
    IN_PROGRESS = 20, _('In Progress'), ColorEnum.warning
    COMPLETE = 50, _('Complete'), ColorEnum.success
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger
```

**Status Groups**:
```python
class MyStatusGroups:
    OPEN = [
        MyStatus.PENDING.value,
        MyStatus.IN_PROGRESS.value
    ]
    COMPLETE = [MyStatus.COMPLETE.value]
    CANCELLED = [MyStatus.CANCELLED.value]
```

#### Custom Status Codes
**Purpose**: Allow users to define custom status codes

**Implementation**:
- Custom statuses stored in database
- Linked to base status codes via `logical_key`
- Custom statuses have unique `key` values
- Custom statuses can override labels and colors

### 9.2 State Transitions

#### TransitionMethod Decorator
```python
@TransitionMethod(
    source=[MyStatus.PENDING, MyStatus.IN_PROGRESS],
    target=MyStatus.COMPLETE,
    method_name='complete'
)
def complete(self, user=None):
    """Complete the order."""
    self.set_status(MyStatus.COMPLETE)
    self.save()
```

**Features**:
- Validates source states
- Calls plugin hooks
- Creates tracking entries
- Returns success/failure

#### StateTransitionMixin
**Purpose**: Enable state transitions on models

**Usage**:
```python
class MyModel(StateTransitionMixin, StatusCodeMixin, models.Model):
    STATUS_CLASS = MyStatus
    
    def complete(self, user=None):
        self.handle_transition(
            current_state=self.status,
            target_state=MyStatus.COMPLETE.value,
            instance=self,
            default_action=self._complete_action,
            user=user
        )
    
    def _complete_action(self):
        self.set_status(MyStatus.COMPLETE)
        self.save()
```

---

## 10. Permissions & Security

### 10.1 Permission System

**Django Auth Framework**:
- Users and Groups
- Permissions linked to models
- Role-based access control

**Ruleset Definition**:
```python
# In users/ruleset.py
class RuleSetEnum(StringEnum):
    PART = 'part'
    STOCK = 'stock'
    ORDER = 'order'
    # ...

RULESET_CHOICES = [
    (RuleSetEnum.PART, _('Parts')),
    (RuleSetEnum.STOCK, _('Stock')),
    # ...
]

def get_ruleset_models():
    return {
        RuleSetEnum.PART: [
            'part_part',
            'part_partcategory',
            'part_bomitem',
        ],
        # ...
    }
```

**Permission Checks**:
```python
# In API views
class PartList(ListCreateAPI):
    role_required = 'part.view'  # GET
    # POST automatically checks 'part.add'
```

### 10.2 Authentication

**Authentication Methods**:
- Session-based (web browser)
- Token-based (API)
- OAuth2 (third-party apps)
- SSO (via django-allauth)
- Magic link (email-based)

**Authentication Backends**:
```python
AUTHENTICATION_BACKENDS = [
    'oauth2_provider.backends.OAuth2Backend',
    'django.contrib.auth.backends.RemoteUserBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'sesame.backends.ModelBackend',  # Magic link
]
```

### 10.3 Security Features

- **CSRF Protection**: Enabled for state-changing operations
- **CORS**: Configurable CORS headers
- **XSS Protection**: Input sanitization
- **SQL Injection**: Django ORM protection
- **Rate Limiting**: Via middleware (optional)
- **MFA**: Multi-factor authentication support
- **Password Policy**: Configurable requirements

---

## 11. Data Flow & Relationships

### 11.1 Core Relationships

#### Part → Stock Flow
```
Part (Catalog)
    ↓
StockItem (Physical)
    ├── Location: StockLocation
    ├── Quantity: Decimal
    └── Status: StockStatus
```

#### Purchase Order Flow
```
PurchaseOrder
    ↓
PurchaseOrderLineItem (Order line)
    ↓
StockItem (Received stock)
    └── purchase_order: PurchaseOrder
```

#### Sales Order Flow
```
SalesOrder
    ↓
SalesOrderLineItem (Order line)
    ↓
SalesOrderAllocation (Allocation)
    ├── line: SalesOrderLineItem
    └── item: StockItem
```

#### Build Order Flow
```
Build
    ├── part: Part (to build)
    └── BuildLine (BOM lines)
        ├── bom_item: BomItem
        └── BuildItem (Allocations)
            ├── build_line: BuildLine
            └── stock_item: StockItem (consumed)
    ↓
StockItem (Output)
    └── build: Build (source)
```

### 11.2 Data Allocation

**Stock Allocation Logic**:
```python
# Available quantity
available = stock_item.quantity - (
    stock_item.build_allocation_count() +
    stock_item.sales_order_allocation_count() +
    stock_item.loan_allocation_count()
)

# Allocate stock
if available >= required_quantity:
    allocation = Allocation.objects.create(
        line=order_line,
        item=stock_item,
        quantity=required_quantity
    )
```

**Allocation Rules**:
- Stock items can be allocated to multiple orders
- Total allocation cannot exceed quantity
- Allocations are checked before allocation
- Allocations are completed when items are shipped/consumed

### 11.3 Stock Consumption

**Build Consumption**:
```python
# Allocate stock
build_item = BuildItem.objects.create(
    build_line=build_line,
    stock_item=stock_item,
    quantity=required_quantity
)

# Complete allocation (consume)
build_item.complete_allocation(
    quantity=required_quantity,
    user=user
)

# Stock item is consumed
stock_item.consumed_by = build
stock_item.quantity = 0  # Or deleted if delete_on_deplete
```

### 11.4 Reference Number Generation

**Pattern System**:
```python
# Setting: PART_REFERENCE_PATTERN
# Pattern: "PART-{ref:04d}"
# Result: "PART-0001", "PART-0002", ...

def generate_next_reference():
    pattern = get_setting('PART_REFERENCE_PATTERN')
    last_ref = Part.objects.aggregate(
        Max('reference_int')
    )['reference_int__max'] or 0
    
    next_num = last_ref + 1
    reference = pattern.format(ref=next_num)
    return reference, next_num
```

---

## 12. Background Tasks & Events

### 12.1 Background Tasks

**Django Q2 Integration**:
```python
from django_q.tasks import schedule, async_task

# Scheduled task
@schedule('hourly')
def check_overdue_orders():
    """Check for overdue orders."""
    overdue = Order.objects.filter(
        due_date__lt=timezone.now().date(),
        status__in=OrderStatusGroups.OPEN
    )
    for order in overdue:
        notify_overdue_order(order)

# Async task
async_task('my_module.my_function', arg1, arg2)
```

**Task Registration**:
```python
# In tasks.py
@scheduled_task(ScheduledTask.DAILY)
def my_daily_task():
    """Run daily."""
    pass

# In apps.py
def tasks():
    """Return list of tasks."""
    return [
        'my_module.tasks.my_daily_task',
    ]
```

### 12.2 Event System

**Event Definition**:
```python
# In events.py
class PartEvents(BaseEventEnum):
    CREATED = 'part.created'
    UPDATED = 'part.updated'
    DELETED = 'part.deleted'
```

**Event Triggering**:
```python
from plugin.events import trigger_event

# Trigger event
trigger_event(
    PartEvents.CREATED,
    part_pk=part.pk,
    user_pk=user.pk
)
```

**Event Listening** (in plugins):
```python
class MyPlugin(EventMixin, InvenTreePlugin):
    def process_event(self, event, *args, **kwargs):
        if event == PartEvents.CREATED:
            part_pk = kwargs.get('part_pk')
            # Handle event
```

### 12.3 Notifications

**Notification System**:
```python
from common.notifications import trigger_notification

trigger_notification(
    instance=order,
    event=OrderEvents.OVERDUE,
    targets=[user1, user2, group1],
    context={
        'message': f'Order {order.reference} is overdue',
        'link': order.get_absolute_url()
    }
)
```

**Notification Types**:
- Email notifications
- In-app notifications
- Webhook notifications (via plugins)

---

## 13. Testing Strategy

### 13.1 Test Structure

**Test Files**:
- `tests.py`: Basic model tests
- `test_api.py`: API endpoint tests
- `test_migrations.py`: Migration tests

**Test Base Classes**:
```python
class InvenTreeAPITestCase(APITestCase):
    """Base class for API tests."""
    
    fixtures = [
        'category',
        'part',
        'company',
        'location',
        'stock',
        'users',
    ]
    
    roles = ['part.view', 'part.add']
```

### 13.2 Test Fixtures

**YAML Format**:
```yaml
- model: part.part
  pk: 1
  fields:
    name: Test Part
    description: Test Description
    category: 1
    active: true
```

**Fixture Location**:
- `app/fixtures/fixture_name.yaml`

### 13.3 Test Patterns

**API Tests**:
```python
class PartAPITest(InvenTreeAPITestCase):
    LIST_URL = reverse('api-part-list')
    
    def test_create_part(self):
        """Test creating a part."""
        data = {
            'name': 'Test Part',
            'category': 1,
        }
        response = self.post(self.LIST_URL, data, expected_code=201)
        self.assertEqual(response.data['name'], 'Test Part')
    
    def test_list_parts(self):
        """Test listing parts."""
        response = self.get(self.LIST_URL)
        self.assertEqual(len(response.data), 1)
```

---

## 14. Deployment & Configuration

### 14.1 Configuration

**config.yaml** (main configuration):
```yaml
database:
  ENGINE: django.db.backends.postgresql
  NAME: inventree
  USER: inventree
  PASSWORD: password
  HOST: localhost
  PORT: 5432

plugins_enabled: true
debug: false
```

**Settings System**:
- Settings defined in `common/setting/`
- Settings can be configured via `config.yaml`
- Settings cached for performance
- Settings validated on load

### 14.2 Database

**Supported Databases**:
- PostgreSQL (recommended)
- MySQL
- SQLite (development only)

**Migrations**:
```bash
# Create migration
python manage.py makemigrations

# Apply migration
python manage.py migrate
```

### 14.3 Deployment Options

**Docker**:
```bash
docker-compose up -d
```

**Bare Metal**:
```bash
# Install script
wget -qO install.sh https://get.inventree.org && bash install.sh
```

**Digital Ocean**:
- One-click deploy via Marketplace

### 14.4 Static Files

**Collection**:
```bash
python manage.py collectstatic
```

**Storage Backends**:
- Local filesystem (default)
- S3 (via django-storages)
- SFTP (via django-storages)

---

## 15. Design Patterns

### 15.1 Model-View-Serializer Pattern

**Django REST Framework Pattern**:
```
Model (Database)
    ↓
Serializer (Data transformation)
    ↓
View (Request handling)
    ↓
Response (JSON)
```

### 15.2 Mixin Pattern

**Purpose**: Reusable functionality across models

**Example**:
```python
class MyModel(
    MetadataMixin,           # JSON metadata
    InvenTreeBarcodeMixin,   # Barcode support
    StatusCodeMixin,          # Status codes
    InvenTreeModel           # Base functionality
):
    pass
```

### 15.3 Registry Pattern

**Plugin Registry**:
```python
class PluginsRegistry:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register_plugin(self, plugin):
        # Register plugin
        pass
```

### 15.4 Factory Pattern

**Reference Generation**:
```python
class ReferenceFactory:
    @staticmethod
    def generate_reference(model_class):
        pattern = model_class.get_reference_pattern()
        # Generate reference
        return reference
```

### 15.5 Observer Pattern

**Event System**:
```python
# Observer (Plugin)
class MyPlugin(EventMixin, InvenTreePlugin):
    def process_event(self, event, *args, **kwargs):
        # Handle event
        pass

# Subject (Event trigger)
trigger_event('part.created', part_pk=part.pk)
```

### 15.6 Strategy Pattern

**Status Transitions**:
```python
# Different strategies for different statuses
@TransitionMethod(source=[Status.PENDING], target=Status.COMPLETE)
def complete(self):
    # Complete strategy
    pass

@TransitionMethod(source=[Status.PENDING], target=Status.CANCELLED)
def cancel(self):
    # Cancel strategy
    pass
```

---

## 16. Key Concepts Explained

This section provides detailed explanations of core concepts, design patterns, and tools used throughout InvenTree. Each concept is explained with its purpose, implementation, and real-world examples from the codebase.

---

### 16.1 Plugins - What Are They For?

**Main Purpose**: Plugins allow extending InvenTree without modifying the core codebase, following the extensibility principle. They enable custom functionality, integrations, and automation while maintaining system stability.

**Problems They Solve**:
1. **Custom Functionality**: Add specific features without touching the core
2. **External Integrations**: Connect with external systems (ERP, MES, CRM, etc.)
3. **Custom Validations**: Implement specific business rules
4. **Custom UI**: Add panels, buttons, navigation items
5. **Automation**: Respond to system events automatically
6. **Third-Party Services**: Integrate payment gateways, shipping providers, etc.

**Architecture Overview**:
```
Plugin Registry
    │
    ├── Plugin Discovery (from plugins/ directory or PyPI)
    ├── Plugin Configuration (stored in database)
    ├── Plugin Initialization (on server startup)
    └── Mixin Registration (capabilities available)
```

**Real Example - Event Plugin**:
```python
# Plugin that listens when a part is created
class MyPlugin(EventMixin, InvenTreePlugin):
    NAME = 'My Plugin'
    SLUG = 'myplugin'
    VERSION = '1.0.0'
    AUTHOR = 'Your Name'
    
    def process_event(self, event, *args, **kwargs):
        if event == 'part_part.created':
            part_id = kwargs.get('id')
            part = Part.objects.get(pk=part_id)
            
            # Do something when a part is created
            # E.g.: Notify external system, create record, etc.
            send_to_external_system(part)
```

**Plugin Types (Mixins)**:

| Mixin | Purpose | Key Methods | Use Case |
|-------|---------|-------------|----------|
| **ActionMixin** | Add action buttons | `get_action_items()` | Custom actions in UI |
| **EventMixin** | Listen to system events | `process_event()`, `wants_process_event()` | React to model changes |
| **NavigationMixin** | Add menu items | `get_navigation_items()` | Custom navigation |
| **PanelMixin** | Add UI panels | `get_panels()` | Custom detail panels |
| **ValidationMixin** | Validate model instances | `validate_model_instance()`, `validate_model_deletion()` | Business rule validation |
| **StateTransitionMixin** | Intercept state changes | `get_transition_handlers()` | Custom state logic |
| **SettingsMixin** | Plugin configuration | `SETTINGS` dict | User-configurable options |
| **URLMixin** | Add custom routes | `get_url_patterns()` | Custom pages |
| **APIMixin** | Add API endpoints | `get_api_endpoints()` | Custom REST endpoints |
| **ReportMixin** | Custom reports | `report_callback()` | Generate custom reports |
| **ScheduleMixin** | Scheduled tasks | `get_scheduled_tasks()` | Background jobs |
| **BarcodeMixin** | Custom barcode formats | `barcode_scan()` | Barcode parsing |

**Plugin Loading Process**:
1. **Discovery**: Scan `plugins/` directory and installed packages
2. **Configuration**: Load from `PluginConfig` model in database
3. **Initialization**: Instantiate plugin class
4. **Mixin Registration**: Register capabilities
5. **Activation**: Enable if `active=True`
6. **Ready**: Plugin available for use

**Plugin File Structure**:
```
myplugin/
├── __init__.py
├── plugin.py          # Main plugin class
├── api.py            # API endpoints (if APIMixin)
├── urls.py           # URL patterns (if URLMixin)
├── templates/        # HTML templates (if needed)
├── static/           # Static files (CSS, JS)
└── setup.py         # Package configuration
```

**Advantages**:
- ✅ **No Core Modification**: Extend functionality without changing core
- ✅ **Easy Installation**: Install via pip or drop in plugins directory
- ✅ **Update Safety**: InvenTree updates don't break plugins
- ✅ **Community Extensions**: Open ecosystem for contributions
- ✅ **Error Isolation**: Plugin errors don't crash system
- ✅ **Configuration**: User-configurable settings
- ✅ **Versioning**: Plugins can track versions independently

### 16.2 Reports - What Are They For?

**Main Purpose**: Generate custom PDF documents (reports and labels) from InvenTree data using HTML templates and WeasyPrint engine.

**Use Cases**:
1. **Order Reports**: Invoices, purchase orders, sales orders, return orders
2. **Labels**: Barcodes, QR codes, location labels, part labels, stock labels
3. **Documentation**: Part reports, stock reports, build reports, assembly guides
4. **Compliance**: Quality certificates, test reports, inspection reports
5. **Shipping**: Packing slips, shipping labels, delivery notes
6. **Inventory**: Stocktake reports, location reports, expiry reports

**Report Types**:
- **Reports**: Full-page documents (invoices, reports)
- **Labels**: Small format labels (barcodes, location tags)

**How It Works**:
```python
# 1. HTML Template (Jinja2/Django template engine)
# report_template.html
<html>
  <head>
    <style>
      body { font-family: Arial; }
      .header { background: #f0f0f0; padding: 20px; }
    </style>
  </head>
  <body>
    <div class="header">
      <h1>Purchase Order: {{ order.reference }}</h1>
      <p>Supplier: {{ order.supplier.name }}</p>
      <p>Date: {{ order.order_date|date:"Y-m-d" }}</p>
    </div>
    <table>
      <thead>
        <tr>
          <th>Part</th>
          <th>Quantity</th>
          <th>Price</th>
        </tr>
      </thead>
      <tbody>
        {% for line in lines %}
        <tr>
          <td>{{ line.part.name }}</td>
          <td>{{ line.quantity }}</td>
          <td>{{ line.purchase_price }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </body>
</html>

# 2. Generation from code
template = ReportTemplate.objects.get(name='Purchase Order')
items = PurchaseOrder.objects.filter(pk=order_id)
output = template.print(items, request=request)

# 3. Result: PDF generated with WeasyPrint
# Stored as DataOutput, downloadable via API
```

**Report System Components**:

| Component | Purpose | Location |
|-----------|---------|----------|
| **ReportTemplate** | Stores HTML templates in database | `report/models.py` |
| **LabelTemplate** | Stores label templates in database | `report/models.py` |
| **WeasyPrint** | Converts HTML/CSS to PDF | External library |
| **ReportContext** | Provides data to templates | `report/mixins.py` |
| **ReportMixin** | Enables report generation on models | `report/mixins.py` |
| **DataOutput** | Stores generated PDF files | `common/models.py` |

**Context Variables Available**:

Each model type provides different context variables:

**PurchaseOrder Context**:
```python
class PurchaseOrderReportContext(BaseReportContext):
    order: PurchaseOrder
    supplier: Company
    lines: QuerySet[PurchaseOrderLineItem]
    tracking: QuerySet[OrderTracking]
    extra_lines: QuerySet[PurchaseOrderExtraLine]

# In template:
{{ order.reference }}
{{ order.order_date }}
{{ supplier.name }}
{{ supplier.address }}
{% for line in lines %}
  {{ line.part.name }}
  {{ line.quantity }}
  {{ line.purchase_price }}
{% endfor %}
```

**Part Context**:
```python
class PartReportContext(BaseReportContext):
    part: Part
    category: PartCategory
    bom_items: QuerySet[BomItem]
    stock_items: QuerySet[StockItem]
    parameters: QuerySet[PartParameter]

# In template:
{{ part.name }}
{{ part.description }}
{{ category.name }}
{% for bom_item in bom_items %}
  {{ bom_item.sub_part.name }} x{{ bom_item.quantity }}
{% endfor %}
```

**StockItem Context**:
```python
class StockItemReportContext(BaseReportContext):
    item: StockItem
    part: Part
    location: StockLocation
    tracking: QuerySet[StockItemTracking]

# In template:
{{ item.serial }}
{{ item.quantity }}
{{ part.name }}
{{ location.name }}
```

**Generation Flow**:
```
1. User selects items (parts, orders, stock items, etc.)
   ↓
2. User selects report/label template
   ↓
3. Frontend calls API: POST /api/report/print/
   ↓
4. Backend creates DataOutput object
   ↓
5. Task offloaded to background worker
   ↓
6. Worker generates PDF using WeasyPrint
   ↓
7. PDF saved to DataOutput.output file
   ↓
8. User downloads via: GET /api/output/{id}/download/
```

**Template Features**:
- **HTML/CSS**: Full HTML and CSS support
- **Django Templates**: Jinja2-style template syntax
- **Context Variables**: Model-specific data available
- **Filters**: Date formatting, number formatting, etc.
- **Conditionals**: `{% if %}`, `{% for %}`, etc.
- **Includes**: Template inheritance and includes

**Label Generation**:
```python
# Labels are smaller, simpler templates
# Example: Barcode label
<div style="width: 2in; height: 1in;">
  <img src="data:image/png;base64,{{ barcode_image }}" />
  <p>{{ part.name }}</p>
  <p>{{ part.IPN }}</p>
</div>
```

### 16.3 Mixins - What Are They For?

**Main Purpose**: Composable reusable functionality without complex multiple inheritance. Allow adding capabilities to models in a modular, maintainable way.

**Problem They Solve**: Instead of creating monolithic base classes with all functionality, mixins allow "mixing" specific functionality. This follows the Single Responsibility Principle and enables better code organization.

**Key Benefits**:
- **Composition Over Inheritance**: Mix capabilities instead of deep inheritance trees
- **Single Responsibility**: Each mixin does one thing well
- **Testability**: Test each mixin independently
- **Flexibility**: Use only what you need
- **Maintainability**: Changes to one mixin don't affect others

**Mixin Example in StockItem**:
```python
class StockItem(
    PluginValidationMixin,                    # Plugin validation hooks
    InvenTreeAttachmentMixin,                # File attachment support
    InvenTreeBarcodeMixin,                    # Barcode/QR code support
    InvenTreeNotesMixin,                      # Rich text notes field
    StatusCodeMixin,                          # Status code management
    report.mixins.InvenTreeReportMixin,       # Report generation capability
    MetadataMixin,                            # JSON metadata for plugins
    InvenTreeTree,                            # Parent-child tree relationships
    common.models.MetaMixin,                   # Updated timestamp
):
    """
    StockItem has ALL these capabilities:
    - Can be validated by plugins
    - Can have file attachments
    - Can have barcodes/QR codes
    - Can have notes
    - Can have status codes
    - Can generate reports
    - Can store plugin metadata
    - Can have parent/child relationships
    - Has updated timestamp
    """
    pass
```

**Complete Mixin Reference**:

#### InvenTreeModel (Base)
**Purpose**: Base class for all InvenTree models
**Location**: `InvenTree/models.py`
**Provides**:
- Plugin validation support
- Field change tracking (DiffMixin)

**Usage**:
```python
class MyModel(InvenTreeModel):
    name = models.CharField(max_length=100)
```

#### MetadataMixin
**Purpose**: JSON metadata field for plugins to store custom data
**Location**: `InvenTree/models.py`
**Fields Added**:
- `metadata`: JSONField (dict)

**Methods**:
- `get_metadata(key, backup_value)`: Get metadata value
- `set_metadata(key, value)`: Set metadata value
- `validate_metadata()`: Validate metadata is a dict

**Usage**:
```python
class Part(MetadataMixin, models.Model):
    name = models.CharField(max_length=100)

# Usage:
part.metadata = {'custom_field': 'value'}
part.set_metadata('plugin_key', {'data': 'value'})
value = part.get_metadata('plugin_key', default={})
```

#### InvenTreeBarcodeMixin
**Purpose**: Barcode and QR code support for models
**Location**: `InvenTree/models.py`
**Fields Added**:
- `barcode_data`: CharField (raw barcode data)
- `barcode_hash`: CharField (hash for matching)

**Required Implementation**:
- `barcode_model_type_code()`: Return 2-character code (e.g., 'ST', 'PT')

**Methods**:
- `format_barcode()`: Format QR code string
- `check_barcode()`: Validate barcode

**Usage**:
```python
class StockItem(InvenTreeBarcodeMixin, models.Model):
    @classmethod
    def barcode_model_type_code(cls):
        return 'ST'  # Stock Item code

# Usage:
# Scan barcode → API matches via barcode_hash
# Generate QR code → Uses format_barcode()
```

#### InvenTreeAttachmentMixin
**Purpose**: File attachment support
**Location**: `InvenTree/models.py`
**Provides**:
- Attachment API endpoints
- Attachment UI components
- File upload handling

**API Endpoints Created**:
- `GET /api/{model}/{id}/attachment/`: List attachments
- `POST /api/{model}/{id}/attachment/`: Upload attachment
- `DELETE /api/{model}/{id}/attachment/{attachment_id}/`: Delete attachment

**Usage**:
```python
class Part(InvenTreeAttachmentMixin, models.Model):
    pass

# Usage:
# Frontend: Upload file via API
# Backend: Automatically handles file storage
```

#### InvenTreeNotesMixin
**Purpose**: Rich text notes field with markdown support
**Location**: `InvenTree/models.py`
**Fields Added**:
- `notes`: TextField (markdown content)

**Features**:
- Markdown rendering
- Rich text editor in UI
- HTML sanitization

**Usage**:
```python
class Part(InvenTreeNotesMixin, models.Model):
    pass

# Usage:
part.notes = "# Heading\n\nSome **bold** text"
# Rendered as HTML in UI
```

#### StatusCodeMixin
**Purpose**: Status code management system
**Location**: `generic/states/states.py`
**Requirements**:
- Model must define `STATUS_CLASS`
- Model must have `status` field (InvenTreeCustomStatusModelField)
- Optional: `status_custom_key` for custom statuses

**Methods**:
- `get_status()`: Get current status code
- `set_status(status)`: Set status code
- `compare_status(status)`: Compare status (handles custom statuses)
- `get_status_display()`: Get human-readable status label

**Usage**:
```python
class PurchaseOrder(StatusCodeMixin, models.Model):
    STATUS_CLASS = PurchaseOrderStatus
    
    status = InvenTreeCustomStatusModelField(
        default=PurchaseOrderStatus.PENDING.value
    )

# Usage:
order.set_status(PurchaseOrderStatus.COMPLETE.value)
current = order.get_status()  # Returns integer
label = order.get_status_display()  # Returns "Complete"
if order.compare_status(PurchaseOrderStatus.PENDING):
    # Handle pending state
```

#### ReferenceIndexingMixin
**Purpose**: Auto-generating reference numbers
**Location**: `InvenTree/models.py`
**Fields Added**:
- `reference`: CharField (auto-generated)
- `reference_int`: BigIntegerField (for sorting)

**Requirements**:
- `REFERENCE_PATTERN_SETTING`: Setting key for pattern
- `validate_reference_field()`: Classmethod to validate reference

**Usage**:
```python
class PurchaseOrder(ReferenceIndexingMixin, models.Model):
    REFERENCE_PATTERN_SETTING = 'PURCHASE_ORDER_REFERENCE_PATTERN'
    
    reference = models.CharField(
        max_length=64,
        unique=True,
        default=generate_next_purchase_order_reference
    )
    reference_int = models.BigIntegerField(default=0)

# Usage:
order = PurchaseOrder.objects.create(supplier=supplier)
# reference automatically set: "PO-0001"
```

#### InvenTreeReportMixin
**Purpose**: Enable report generation for models
**Location**: `report/mixins.py`
**Requirements**:
- Model must define `report_context()` method
- Returns a TypedDict with context variables

**Usage**:
```python
class PurchaseOrder(InvenTreeReportMixin, models.Model):
    def report_context(self) -> PurchaseOrderReportContext:
        return {
            'order': self,
            'supplier': self.supplier,
            'lines': self.lines.all(),
            'tracking': self.tracking.all(),
        }

# Usage:
# Enables report generation in UI
# Template can access: {{ order }}, {{ supplier }}, etc.
```

#### InvenTreeTree (MPTT)
**Purpose**: Parent-child tree relationships
**Location**: `InvenTree/models.py` (uses django-mptt)
**Provides**:
- Tree structure (parent/children)
- Tree traversal methods
- Tree queries (ancestors, descendants, etc.)

**Usage**:
```python
class StockItem(InvenTreeTree, models.Model):
    parent = TreeForeignKey('self', null=True, blank=True)
    
    # Usage:
    item.get_ancestors()  # All parents
    item.get_descendants()  # All children
    item.get_root()  # Top-level parent
```

#### PluginValidationMixin
**Purpose**: Allow plugins to validate model instances
**Location**: `InvenTree/models.py`
**Hooks**:
- `full_clean()`: Calls plugin validators
- `save()`: Calls plugin validators before save
- `delete()`: Calls plugin validators before delete

**Usage**:
```python
class Part(PluginValidationMixin, models.Model):
    name = models.CharField(max_length=100)

# Plugins can validate:
# - Before save (validate_model_instance)
# - Before delete (validate_model_deletion)
```

**Mixin Composition Pattern**:
```python
# Mixins are applied left-to-right
class MyModel(
    MixinA,  # Applied first
    MixinB,  # Applied second
    MixinC,  # Applied third
    models.Model  # Base class
):
    # Method Resolution Order (MRO):
    # MyModel → MixinC → MixinB → MixinA → models.Model
    pass
```

**Mixin Best Practices**:
- ✅ Keep mixins focused on single responsibility
- ✅ Document required methods/properties
- ✅ Use abstract base classes when appropriate
- ✅ Test mixins independently
- ✅ Avoid circular dependencies
- ✅ Use descriptive names

**Common Mixin Combinations**:
```python
# Standard model with common features
class StandardModel(
    MetadataMixin,
    InvenTreeNotesMixin,
    InvenTreeAttachmentMixin,
    InvenTreeModel
):
    pass

# Model with status codes
class StatusModel(
    StatusCodeMixin,
    StateTransitionMixin,
    StandardModel
):
    pass

# Model with reports
class ReportableModel(
    InvenTreeReportMixin,
    StandardModel
):
    pass
```

### 16.4 State Management in Backend - What Is It For?

**Main Purpose**: Control and track object states (orders, builds, stock items) consistently with validation.

**Problem It Solves**: Without a state system, objects can be in inconsistent states. For example, a purchase order could be "complete" but without received items.

**System Components**:

#### StatusCode (State Definition)
```python
class PurchaseOrderStatus(StatusCode):
    """Statuses for PurchaseOrder."""
    
    PENDING = 10, _('Pending'), ColorEnum.info
    APPROVED = 20, _('Approved'), ColorEnum.success
    PLACED = 30, _('Placed'), ColorEnum.warning
    RECEIVED = 40, _('Received'), ColorEnum.success
    COMPLETE = 50, _('Complete'), ColorEnum.success
    CANCELLED = 60, _('Cancelled'), ColorEnum.danger

# Usage:
status = PurchaseOrderStatus.PENDING
print(status.value)  # 10
print(status.label)   # "Pending"
print(status.color)   # "info"
```

#### StatusCodeMixin (State Management)
```python
class PurchaseOrder(StatusCodeMixin, models.Model):
    STATUS_CLASS = PurchaseOrderStatus
    
    status = InvenTreeCustomStatusModelField(
        default=PurchaseOrderStatus.PENDING.value
    )

# Available methods:
order.set_status(PurchaseOrderStatus.APPROVED.value)
current_status = order.get_status()  # 20
order.compare_status(PurchaseOrderStatus.PENDING.value)  # False
```

#### Status Groups (Filtering)
```python
class PurchaseOrderStatusGroups:
    OPEN = [
        PurchaseOrderStatus.PENDING.value,
        PurchaseOrderStatus.APPROVED.value,
        PurchaseOrderStatus.PLACED.value,
    ]
    COMPLETE = [PurchaseOrderStatus.COMPLETE.value]

# Usage:
open_orders = PurchaseOrder.objects.filter(
    status__in=PurchaseOrderStatusGroups.OPEN
)
```

**Advantages**:
- **Consistency**: Defined and validated states
- **UI**: Automatic colors for states
- **Filtering**: Easy to filter by state groups
- **Customization**: Users can create custom states
- **History**: Can track state changes

### 16.5 State Transitions - What Are They and What Are They For?

**Main Purpose**: Control transitions between states safely, with validation and plugin hooks.

**Problem It Solves**: Allows defining which transitions are valid and executing custom logic during transitions.

**How It Works**:

#### TransitionMethod Decorator
```python
class PurchaseOrder(StateTransitionMixin, StatusCodeMixin, models.Model):
    
    @TransitionMethod(
        source=[PurchaseOrderStatus.PENDING, PurchaseOrderStatus.APPROVED],
        target=PurchaseOrderStatus.PLACED,
        method_name='place_order'
    )
    def place_order(self, user=None):
        """Place the order (send to supplier)."""
        # Validate that it can be placed
        if not self.can_place():
            raise ValidationError("Cannot place order")
        
        # Change state
        self.set_status(PurchaseOrderStatus.PLACED)
        self.placed_date = timezone.now().date()
        self.save()
        
        # Create tracking entry
        OrderTracking.objects.create(
            order=self,
            tracking_type=OrderTrackingCode.PLACED,
            user=user,
            notes='Order placed'
        )
```

#### StateTransitionMixin (Processing)
```python
# When you call place_order():
order.place_order(user=request.user)

# Internally does:
def handle_transition(self, current_state, target_state, instance, default_action, **kwargs):
    # 1. Find plugins that listen to transitions
    transition_plugins = registry.with_mixin(PluginMixinEnum.STATE_TRANSITION)
    
    # 2. Execute plugin handlers
    for plugin in transition_plugins:
        handlers = plugin.get_transition_handlers()
        for handler in handlers:
            result = handler.transition(
                current_state, target_state, instance, default_action, **kwargs
            )
            if result:
                return result  # Plugin handled the transition
    
    # 3. If no plugin handled it, execute default action
    return default_action(current_state, target_state, instance, **kwargs)
```

**Example Plugin Intercepting Transitions**:
```python
class OrderValidationPlugin(StateTransitionMixin, InvenTreePlugin):
    def get_transition_handlers(self):
        return [
            PurchaseOrderPlaceTransitionHandler()
        ]

class PurchaseOrderPlaceTransitionHandler(TransitionMethod):
    def transition(self, current_state, target_state, instance, default_action, **kwargs):
        # Only intercept transitions to PLACED
        if target_state != PurchaseOrderStatus.PLACED.value:
            return False  # Not interested
        
        # Validate that it has items
        if instance.lines.count() == 0:
            raise ValidationError("Order must have line items")
        
        # Allow normal transition to continue
        return False  # Let default method execute
```

**Advantages**:
- **Validation**: Ensure only valid transitions occur
- **Extensibility**: Plugins can intercept transitions
- **Audit Trail**: Automatic tracking of state changes
- **Centralized Logic**: Transitions defined in one place

### 16.6 Factories - What Are They?

**Main Purpose**: Create complex objects consistently, especially for auto-generated reference numbers.

**In InvenTree**: The Factory pattern is used mainly to generate reference numbers for orders, builds, parts, etc.

**Real Example - Reference Factory**:
```python
# In order/validators.py
def generate_next_purchase_order_reference():
    """Generate the next available PurchaseOrder reference."""
    pattern = get_setting('PURCHASE_ORDER_REFERENCE_PATTERN', 'PO-{ref:04d}')
    
    # Get last reference number
    last_ref = PurchaseOrder.objects.aggregate(
        Max('reference_int')
    )['reference_int__max'] or 0
    
    # Increment
    next_num = last_ref + 1
    
    # Format according to pattern
    reference = pattern.format(ref=next_num)
    
    return reference, next_num

# Automatic usage:
class PurchaseOrder(ReferenceIndexingMixin, models.Model):
    REFERENCE_PATTERN_SETTING = 'PURCHASE_ORDER_REFERENCE_PATTERN'
    
    reference = models.CharField(
        max_length=64,
        unique=True,
        default=generate_next_purchase_order_reference,
        validators=[validate_purchase_order_reference]
    )
    reference_int = models.BigIntegerField(default=0)

# When creating an order:
order = PurchaseOrder.objects.create(supplier=supplier)
# reference is automatically generated: "PO-0001", "PO-0002", etc.
```

**Reference Patterns**:
```python
# Configuration in settings:
PURCHASE_ORDER_REFERENCE_PATTERN = 'PO-{ref:04d}'
# Result: PO-0001, PO-0002, PO-0003

PURCHASE_ORDER_REFERENCE_PATTERN = 'PUR-{year}-{ref:05d}'
# Result: PUR-2025-00001, PUR-2025-00002

PURCHASE_ORDER_REFERENCE_PATTERN = 'PO-{ref}'
# Result: PO-1, PO-2, PO-3
```

**Advantages**:
- **Consistency**: All numbers follow the same format
- **Configurability**: Users can change the pattern
- **Uniqueness**: Guarantees unique references
- **Sorting**: `reference_int` allows numeric sorting

### 16.7 Observer Pattern - How Does It Work?

**Main Purpose**: Allow plugins to "subscribe" to system events and react when events occur.

**Implementation in InvenTree**:

#### 1. Trigger Event (Subject)
```python
# Anywhere in code:
from plugin.events import trigger_event

# When creating a part:
part = Part.objects.create(name='New Part', category=category)
trigger_event('part_part.created', model='part', id=part.pk)

# When updating an order:
order.status = PurchaseOrderStatus.COMPLETE
order.save()
trigger_event('order_purchaseorder.updated', model='order', id=order.pk)
```

#### 2. Event Registration
```python
# In plugin/base/event/events.py
def register_event(event, *args, **kwargs):
    """Register event and notify plugins."""
    
    # Find plugins that listen to events
    for plugin in registry.with_mixin(PluginMixinEnum.EVENTS, active=True):
        # Check if plugin wants to process this event
        if not plugin.wants_process_event(event):
            continue
        
        # Execute plugin callback in background worker
        offload_task(
            process_event, 
            plugin.slug, 
            event, 
            *args, 
            **kwargs
        )
```

#### 3. Plugin Observer (Observer)
```python
# Plugin that observes events
class MyObserverPlugin(EventMixin, InvenTreePlugin):
    NAME = 'Observer Plugin'
    SLUG = 'observer'
    
    def wants_process_event(self, event: str) -> bool:
        """Only listen to part events."""
        return event.startswith('part_')
    
    def process_event(self, event: str, *args, **kwargs):
        """Process event."""
        if event == 'part_part.created':
            part_id = kwargs.get('id')
            part = Part.objects.get(pk=part_id)
            
            # Do something when a part is created
            logger.info(f'New part created: {part.name}')
            send_notification(f'New part: {part.name}')
            
        elif event == 'part_part.updated':
            part_id = kwargs.get('id')
            part = Part.objects.get(pk=part_id)
            
            # Do something when a part is updated
            logger.info(f'Part updated: {part.name}')
            sync_to_external_system(part)
```

#### 4. Event Flow
```
┌─────────────┐
│ Model Save  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ trigger_event() │ ◄─── Trigger event
└──────┬──────────┘
       │
       ▼
┌──────────────────┐
│ register_event() │ ◄─── Register event
└──────┬───────────┘
       │
       ▼
┌──────────────────────────┐
│ Find Plugins with        │
│ EventMixin active        │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│ plugin.wants_process_    │
│ event(event) ?           │
└──────┬───────────────────┘
       │
       ▼ (If True)
┌──────────────────────────┐
│ offload_task(            │
│   process_event,         │
│   plugin.slug,           │
│   event, ...             │
│ )                        │
└──────┬───────────────────┘
       │
       ▼ (Background Worker)
┌──────────────────────────┐
│ plugin.process_event()   │ ◄─── Plugin reacts
└──────────────────────────┘
```

**Available Events**:
```python
# Generic events (automatic):
'part_part.created'      # When a part is created
'part_part.updated'       # When a part is updated
'part_part.deleted'      # When a part is deleted
'stock_stockitem.created' # When a stock item is created
'order_purchaseorder.created' # When an order is created

# Custom events (manual):
'build.build.completed'  # When a build is completed
'order.purchaseorder.received' # When an order is received
'stock.stockitem.low_stock' # When stock is low
```

**Real Example - Notification Plugin**:
```python
class NotificationPlugin(EventMixin, InvenTreePlugin):
    def process_event(self, event, *args, **kwargs):
        if event == 'order_purchaseorder.completed':
            order_id = kwargs.get('id')
            order = PurchaseOrder.objects.get(pk=order_id)
            
            # Send email to supplier
            send_email(
                to=order.supplier.contact_email,
                subject=f'Order {order.reference} Completed',
                body=f'Order {order.reference} has been marked as complete.'
            )
        
        elif event == 'stock_stockitem.low_stock':
            stock_id = kwargs.get('id')
            stock = StockItem.objects.get(pk=stock_id)
            
            # Notify administrators
            notify_admins(f'Low stock: {stock.part.name} at {stock.location.name}')
```

**Observer Pattern Advantages**:
- **Decoupling**: Code that triggers events doesn't know about observers
- **Extensibility**: Easy to add new observers (plugins)
- **Flexibility**: Multiple plugins can react to the same event
- **Asynchronous**: Events processed in background worker
- **Audit**: All events can be logged

### 16.8 Invoke Tasks - Command Line Interface

**Main Purpose**: InvenTree uses the [Invoke](https://www.pyinvoke.org/) tool to provide a comprehensive command-line interface for system administration, development, and maintenance tasks.

**What Is Invoke?**: Invoke is a Python-based task execution tool that allows creating custom tasks and command-line utilities. It provides a clean, organized way to manage all administrative operations.

**Why Use Invoke?**: 
- **Standardized Interface**: All administrative tasks accessible through a single command
- **Task Dependencies**: Tasks can depend on other tasks (pre/post hooks)
- **Environment Detection**: Automatically detects Docker, devcontainer, package installer environments
- **Error Handling**: Consistent error messages and logging
- **Documentation**: Built-in help system for all tasks

**Task Categories**:

InvenTree organizes tasks into three collections:
1. **Main Tasks** (`invoke <task>`): Production and common operations
2. **Development Tasks** (`invoke dev.<task>`): Development-only operations
3. **Internal Tasks** (`invoke int.<task>`): Internal operations called by other tasks

#### 16.8.1 Main Invoke Tasks

**Installation & Setup**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `install` | `invoke install` | Install required Python packages | `--uv`, `--skip_plugins` |
| `plugins` | `invoke plugins` | Install plugins from `plugins.txt` | `--uv` |
| `update` | `invoke update` | Complete system update | `--skip_backup`, `--frontend`, `--no_frontend`, `--skip_static`, `--uv` |
| `migrate` | `invoke migrate` | Run database migrations | (auto runs rebuild_models, rebuild_thumbnails) |
| `superuser` | `invoke superuser` | Create admin user account | Interactive |

**Server Operations**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `server` | `invoke dev.server` | Start development server | `--address`, `--no_reload`, `--no_threading` |
| `gunicorn` | `invoke dev.gunicorn` | Start production server | `--address`, `--workers` |
| `worker` | `invoke worker` | Start background worker | None |
| `monitor` | `invoke monitor` | Monitor worker performance | None |
| `wait` | `invoke wait` | Wait for database connection | None |

**Data Management**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `backup` | `invoke backup` | Backup database and media | `--clean`, `--compress`, `--encrypt`, `--path`, `--quiet`, `--skip_db`, `--skip_media` |
| `restore` | `invoke restore` | Restore from backup | `--path`, `--db_file`, `--media_file`, `--decrypt`, `--skip_db`, `--skip_media`, `--uncompress` |
| `listbackups` | `invoke listbackups` | List available backups | None |
| `export_records` | `invoke export_records` | Export database to JSON | `--filename`, `--overwrite`, `--include_permissions`, `--include_tokens`, `--exclude_plugins`, `--include_sso`, `--include_session`, `--retain_temp` |
| `import_records` | `invoke import_records` | Import database from JSON | `--filename`, `--clear`, `--retain_temp` |

**Frontend Operations**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `frontend_download` | `invoke frontend_download` | Download pre-built frontend | `--ref`, `--tag`, `--file`, `--repo`, `--extract`, `--clean` |
| `frontend_compile` | `invoke int.frontend_compile` | Compile React frontend | `--extract` |
| `frontend_install` | `invoke int.frontend_install` | Install frontend dependencies | None |
| `frontend_trans` | `invoke int.frontend_trans` | Compile frontend translations | `--extract` |
| `frontend_build` | `invoke int.frontend_build` | Build frontend for production | None |
| `frontend_server` | `invoke dev.frontend_server` | Start frontend dev server | None |
| `frontend_test` | `invoke dev.frontend_test` | Run Playwright tests | `--host` |

**Maintenance**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `static` | `invoke static` | Collect static files | `--frontend`, `--clear`, `--skip_plugins` |
| `rebuild_models` | `invoke int.rebuild_models` | Rebuild MPTT tree structures | None |
| `rebuild_thumbnails` | `invoke int.rebuild_thumbnails` | Rebuild image thumbnails | None |
| `clean_settings` | `invoke int.clean_settings` | Remove old undefined settings | None |
| `clear_generated` | `invoke int.clear_generated` | Clear generated files | None |

**Development & Testing**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `setup_dev` | `invoke dev.setup_dev` | Setup development environment | `--tests` |
| `setup_test` | `invoke dev.setup_test` | Setup test environment with demo data | `--ignore_update`, `--dev`, `--validate_files`, `--use_ssh`, `--path` |
| `test` | `invoke dev.test` | Run unit tests | `--check`, `--disable_pty`, `--runtest`, `--migrations`, `--report`, `--coverage`, `--translations`, `--keepdb` |
| `shell` | `invoke dev.shell` | Launch Django shell | None |
| `schema` | `invoke dev.schema` | Export API schema | `--filename`, `--overwrite`, `--no_default` |
| `translate` | `invoke dev.translate` | Rebuild translation files | `--ignore_static`, `--no_frontend` |
| `test_translations` | `invoke dev.test_translations` | Test translation system | None |

**Documentation**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `build_docs` | `invoke build_docs` | Build documentation | `--mkdocs` |
| `docs_server` | `invoke dev.docs_server` | Start local docs server | `--address`, `--compile_schema` |

**Utilities**:

| Task | Command | Purpose | Options |
|------|---------|---------|---------|
| `version` | `invoke version` | Show InvenTree version info | None (default task) |
| `remove_mfa` | `invoke remove_mfa` | Remove MFA for a user | `--mail` |
| `showmigrations` | `invoke int.showmigrations` | Show migration status | `--app` |
| `export_definitions` | `invoke int.export_definitions` | Export all definitions | `--basedir` |
| `export_settings_definitions` | `invoke int.export_settings_definitions` | Export settings definitions | `--filename`, `--overwrite` |

#### 16.8.2 Common Task Workflows

**Initial Installation**:
```bash
# 1. Install dependencies
invoke install

# 2. Run migrations
invoke migrate

# 3. Create admin user
invoke superuser

# 4. Collect static files
invoke static --frontend

# 5. Start server
invoke dev.server
```

**System Update**:
```bash
# Complete update (includes backup, migrate, frontend, static)
invoke update

# Update without backup (advanced)
invoke update --skip_backup

# Update without frontend compilation (Docker)
invoke update --no_frontend
```

**Development Setup**:
```bash
# Setup development environment
invoke dev.setup_dev

# Setup with test data
invoke dev.setup_test --path inventree-demo-dataset

# Run tests
invoke dev.test --runtest=part.test_api

# Run with coverage
invoke dev.test --coverage
```

**Backup & Restore**:
```bash
# Create backup
invoke backup --compress --encrypt

# List backups
invoke listbackups

# Restore from backup
invoke restore --path /path/to/backups --db_file backup.db.gz
```

**Data Export/Import**:
```bash
# Export all data
invoke export_records --filename data.json --overwrite

# Import data
invoke import_records --filename data.json --clear
```

#### 16.8.3 Task Dependencies & Hooks

**Pre-Tasks** (run before main task):
```python
@task(pre=[wait])
def server(c):
    # wait task runs first
    pass
```

**Post-Tasks** (run after main task):
```python
@task(post=[rebuild_models, rebuild_thumbnails])
def migrate(c):
    # rebuild_models and rebuild_thumbnails run after migrate
    pass
```

**Example with Both**:
```python
@task(
    pre=[wait],
    post=[static, server]
)
def test_translations(c):
    # wait runs first, then test_translations, then static and server
    pass
```

#### 16.8.4 Management Commands

InvenTree also provides Django management commands (via `python manage.py`):

**Database Commands**:
- `wait_for_db`: Wait for database connection
- `runmigrations`: Run migrations with maintenance mode
- `check_migrations`: Check for pending migrations
- `rebuild_models`: Rebuild MPTT tree structures
- `rebuild_thumbnails`: Rebuild image thumbnails

**Plugin Commands**:
- `collectplugins`: Collect plugin static files

**Export Commands**:
- `export_settings_definitions`: Export settings to JSON
- `export_tags`: Export tag definitions to YAML
- `export_filters`: Export filter definitions to YAML
- `export_report_context`: Export report context to JSON

**Schema Commands**:
- `schema`: Export OpenAPI schema

**Utilities**:
- `clean_settings`: Remove undefined settings
- `remove_mfa`: Remove MFA for a user
- `migrate_icons`: Migrate icon references

**Usage**:
```bash
# Via manage.py
python manage.py rebuild_models

# Via invoke (wraps manage.py)
invoke int.rebuild_models
```

#### 16.8.5 Task Execution Flow

```
User runs: invoke update
    │
    ▼
┌─────────────────────────┐
│ Environment Checks      │
│ - Python version        │
│ - Invoke version        │
│ - Invoke path           │
│ - Environment type      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Pre-Tasks (if any)     │
│ - wait (if specified)  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Main Task Execution     │
│ - install              │
│ - backup (optional)    │
│ - migrate              │
│ - frontend_compile     │
│ - static               │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Post-Tasks (if any)     │
│ - clean_settings        │
└─────────────────────────┘
```

#### 16.8.6 Environment Detection

Invoke automatically detects the environment:

**Docker Environment**:
- Detects `INVENTREE_DOCKER` env var
- Skips frontend compilation by default
- Uses container-specific paths

**DevContainer Environment**:
- Detects `INVENTREE_DEVCONTAINER` env var
- Optimized for VS Code development

**Package Installer**:
- Detects `INVENTREE_PKG_INSTALLER` env var
- Uses `inventree run invoke` prefix

**ReadTheDocs**:
- Detects `READTHEDOCS` env var
- Skips certain operations

**Example**:
```python
if is_docker_environment():
    # Skip frontend compilation
    frontend = False
elif is_pkg_installer():
    # Use package installer paths
    cmd = 'inventree run invoke update'
```

#### 16.8.7 Task Help System

**List All Tasks**:
```bash
invoke --list
```

**Get Task Help**:
```bash
invoke update --help
```

**Output**:
```
Usage: invoke[options] update [--skip-backup] [--frontend] 
                                  [--no-frontend] [--skip-static] 
                                  [--uv]

Update InvenTree installation.

Options:
  --skip-backup      Skip database backup step (advanced users)
  --frontend         Force frontend compilation/download step
  --no-frontend      Skip frontend compilation/download step
  --skip-static      Skip static file collection step
  --uv               Use UV (experimental package manager)
```

#### 16.8.8 Task Best Practices

**When to Use Invoke Tasks**:
- ✅ System administration (backup, restore, update)
- ✅ Development workflows (setup, test, server)
- ✅ Maintenance operations (migrate, rebuild, clean)
- ✅ Data operations (export, import)
- ✅ Frontend operations (compile, build, download)

**When to Use Django Management Commands**:
- ✅ Direct database operations
- ✅ Model-specific operations
- ✅ One-off scripts
- ✅ Operations that need direct Django access

**Task Organization**:
- **Main tasks**: Production-ready, well-documented
- **Dev tasks**: Development-only, may modify data
- **Internal tasks**: Called by other tasks, not for direct use

**Error Handling**:
- Tasks automatically handle errors and provide helpful messages
- Failed tasks exit with non-zero status codes
- Environment checks prevent invalid operations

---

## 17. Conclusion

This document provides a comprehensive overview of the InvenTree architecture, design patterns, and implementation details. The system is built on Django and React, with a modular architecture that allows for extensibility through plugins.

**Key Takeaways**:
1. **Modular Design**: Each module is self-contained with models, serializers, API views, and tests
2. **Mixin Pattern**: Reusable functionality via mixins (metadata, barcodes, status codes, etc.)
3. **Plugin System**: Extensible architecture for custom functionality
4. **Status Code System**: Flexible status management with custom status support
5. **State Transitions**: Controlled state changes with plugin hooks
6. **Permission System**: Role-based access control via rulesets
7. **API-First**: RESTful API for all functionality
8. **Frontend-Backend Separation**: React frontend communicates via REST API

**For Developers**:
- Follow existing patterns when adding new modules
- Use mixins for common functionality
- Implement proper permissions and validation
- Write comprehensive tests
- Document code and APIs
- Follow Django and React best practices

---

*Document Version: 1.0*  
*Last Updated: 2025-11-05*  
*Status: Comprehensive Architecture Documentation - Complete*

