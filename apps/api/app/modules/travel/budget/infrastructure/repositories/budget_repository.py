"""SQLAlchemyTripBudgetRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.query import exclude_deleted
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.budget_status import BudgetStatus
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.budget.infrastructure.models.budget_model import (
    BudgetCategoryModel,
    ExpenseModel,
    TripBudgetModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class SQLAlchemyTripBudgetRepository:
    """SQLAlchemy implementation of ITripBudgetRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, budget_id: BudgetId) -> TripBudget | None:
        """Find budget by ID. Soft-deleted ones are returned."""
        stmt = (
            select(TripBudgetModel)
            .where(TripBudgetModel.id == budget_id.value)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        """Find the latest active (non-deleted) budget for a trip."""
        stmt = (
            select(TripBudgetModel)
            .where(TripBudgetModel.trip_id == trip_id.value)
        )
        stmt = exclude_deleted(stmt, TripBudgetModel)
        stmt = (
            stmt.order_by(TripBudgetModel.created_at.desc(), TripBudgetModel.id.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def save(self, budget: TripBudget) -> None:
        """Persist/update budget aggregate."""
        stmt = select(TripBudgetModel).where(TripBudgetModel.id == budget.budget_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            # Insert new budget
            model = self._to_new_model(budget)
            self._session.add(model)
        else:
            # Update existing budget
            self._apply_to_existing(budget, model)

    async def delete(self, budget_id: BudgetId) -> None:
        """Hard-delete a budget row."""
        stmt = select(TripBudgetModel).where(TripBudgetModel.id == budget_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)

    async def exists(self, budget_id: BudgetId) -> bool:
        """Check if budget exists and is not soft-deleted."""
        stmt = (
            select(TripBudgetModel.id)
            .where(TripBudgetModel.id == budget_id.value)
        )
        stmt = exclude_deleted(stmt, TripBudgetModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Check if a non-deleted budget exists for the trip."""
        stmt = (
            select(TripBudgetModel.id)
            .where(TripBudgetModel.trip_id == trip_id.value)
        )
        stmt = exclude_deleted(stmt, TripBudgetModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    # ------------------------------------------------------------------ #
    # Domain Mapping Helpers                                             #
    # ------------------------------------------------------------------ #

    def _to_domain(self, model: TripBudgetModel) -> TripBudget:
        """Convert ORM model to domain aggregate root."""
        # Convert categories
        categories = [
            BudgetCategory(
                entity_id=CategoryId(model_cat.id),
                name=model_cat.name,
                description=model_cat.description,
                icon=model_cat.icon,
                created_at=model_cat.created_at,
                updated_at=model_cat.updated_at,
            )
            for model_cat in model.categories
        ]

        # Convert expenses
        expenses = [
            Expense(
                entity_id=ExpenseId(model_exp.id),
                title=model_exp.title,
                amount=Money(
                    amount=model_exp.amount,
                    currency=CurrencyCode(model_exp.currency),
                ),
                category_id=CategoryId(model_exp.category_id),
                expense_type=ExpenseType(model_exp.expense_type),
                description=model_exp.description,
                expense_date=model_exp.expense_date,
                created_at=model_exp.created_at,
                updated_at=model_exp.updated_at,
            )
            for model_exp in model.expenses
        ]

        budget_limit = Money(
            amount=model.limit_amount,
            currency=CurrencyCode(model.currency),
        )

        # Calculate exceeded thresholds based on total spent vs limit
        total_spent = sum(e.amount.amount for e in expenses)
        exceeded_thresholds = set()
        if budget_limit.amount > 0:
            percentage = (total_spent / budget_limit.amount) * 100
            for threshold in (50, 75, 90, 100):
                if percentage >= threshold:
                    exceeded_thresholds.add(threshold)

        budget = TripBudget(
            entity_id=BudgetId(model.id),
            trip_id=TripId(model.trip_id),
            owner_id=UserId(model.owner_id),
            limit=budget_limit,
            status=BudgetStatus(model.status),
            categories=categories,
            expenses=expenses,
            exceeded_thresholds=exceeded_thresholds,
            version=model.version,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

        # Clear pending events as we just loaded it from persistence
        budget.pop_events()
        return budget

    def _to_new_model(self, budget: TripBudget) -> TripBudgetModel:
        """Map brand-new domain aggregate to SQLAlchemy ORM model."""
        model = TripBudgetModel(
            id=budget.budget_id.value,
            trip_id=budget.trip_id.value,
            owner_id=budget.owner_id.value,
            limit_amount=budget.limit.amount,
            currency=str(budget.limit.currency),
            status=budget.status.value,
            version=budget.version,
            deleted_at=budget.deleted_at,
            created_at=budget.created_at,
            updated_at=budget.updated_at,
        )

        model.categories = [
            BudgetCategoryModel(
                id=c.entity_id.value,
                budget_id=model.id,
                name=c.name,
                description=c.description,
                icon=c.icon,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in budget.categories
        ]

        model.expenses = [
            ExpenseModel(
                id=e.entity_id.value,
                budget_id=model.id,
                title=e.title,
                amount=e.amount.amount,
                currency=str(e.amount.currency),
                category_id=e.category_id.value,
                expense_type=e.expense_type.value,
                description=e.description,
                expense_date=e.expense_date,
                created_at=e.created_at,
                updated_at=e.updated_at,
            )
            for e in budget.expenses
        ]

        return model

    def _apply_to_existing(self, budget: TripBudget, model: TripBudgetModel) -> None:
        """Merge modifications from domain aggregate to existing ORM model."""
        model.limit_amount = budget.limit.amount
        model.currency = str(budget.limit.currency)
        model.status = budget.status.value
        model.deleted_at = budget.deleted_at
        model.updated_at = budget.updated_at
        model.version = budget.version

        # Sync categories (insert, update, delete-orphan)
        existing_categories = {c.id: c for c in model.categories}
        new_categories = []
        for domain_cat in budget.categories:
            cat_id = domain_cat.entity_id.value
            if cat_id in existing_categories:
                cat_model = existing_categories[cat_id]
                cat_model.name = domain_cat.name
                cat_model.description = domain_cat.description
                cat_model.icon = domain_cat.icon
                cat_model.updated_at = domain_cat.updated_at
            else:
                cat_model = BudgetCategoryModel(
                    id=cat_id,
                    budget_id=model.id,
                    name=domain_cat.name,
                    description=domain_cat.description,
                    icon=domain_cat.icon,
                    created_at=domain_cat.created_at,
                    updated_at=domain_cat.updated_at,
                )
            new_categories.append(cat_model)
        model.categories = new_categories

        # Sync expenses (insert, update, delete-orphan)
        existing_expenses = {e.id: e for e in model.expenses}
        new_expenses = []
        for domain_exp in budget.expenses:
            exp_id = domain_exp.entity_id.value
            if exp_id in existing_expenses:
                exp_model = existing_expenses[exp_id]
                exp_model.title = domain_exp.title
                exp_model.amount = domain_exp.amount.amount
                exp_model.currency = str(domain_exp.amount.currency)
                exp_model.category_id = domain_exp.category_id.value
                exp_model.expense_type = domain_exp.expense_type.value
                exp_model.description = domain_exp.description
                exp_model.expense_date = domain_exp.expense_date
                exp_model.updated_at = domain_exp.updated_at
            else:
                exp_model = ExpenseModel(
                    id=exp_id,
                    budget_id=model.id,
                    title=domain_exp.title,
                    amount=domain_exp.amount.amount,
                    currency=str(domain_exp.amount.currency),
                    category_id=domain_exp.category_id.value,
                    expense_type=domain_exp.expense_type.value,
                    description=domain_exp.description,
                    expense_date=domain_exp.expense_date,
                    created_at=domain_exp.created_at,
                    updated_at=domain_exp.updated_at,
                )
            new_expenses.append(exp_model)
        model.expenses = new_expenses
