/**
 * Budget & Expense API Service.
 *
 * Connects directly to FastAPI Travel Budget endpoints:
 * - POST   /api/v1/trips/{trip_id}/budget (Create budget)
 * - GET    /api/v1/trips/{trip_id}/budget (Get budget or summary)
 * - PATCH  /api/v1/trips/{trip_id}/budget (Update budget limit/status)
 * - GET    /api/v1/trips/{trip_id}/budget/expenses (List expenses)
 * - POST   /api/v1/trips/{trip_id}/budget/expenses (Add expense)
 * - PATCH  /api/v1/trips/{trip_id}/budget/expenses/{expense_id} (Update expense)
 * - DELETE /api/v1/trips/{trip_id}/budget/expenses/{expense_id} (Delete expense)
 */

import { apiClient } from "@/core/api/client";
import {
  BudgetResponse,
  BudgetSummaryResponse,
  BudgetCreateRequest,
  BudgetUpdateRequest,
  ExpenseResponse,
  ExpenseListResponse,
  ExpenseCreateRequest,
  ExpenseUpdateRequest,
} from "@/core/api/types";

export const BudgetApi = {
  /**
   * Create a budget for a trip.
   */
  async createBudget(
    tripId: string,
    payload: BudgetCreateRequest
  ): Promise<BudgetResponse> {
    return apiClient.post<BudgetResponse>(
      `/trips/${tripId}/budget`,
      payload
    );
  },

  /**
   * Get budget details for a trip.
   */
  async getBudget(tripId: string): Promise<BudgetResponse> {
    return apiClient.get<BudgetResponse>(
      `/trips/${tripId}/budget`
    );
  },

  /**
   * Get complete budget summary including category and type breakdowns.
   */
  async getBudgetSummary(tripId: string): Promise<BudgetSummaryResponse> {
    return apiClient.get<BudgetSummaryResponse>(
      `/trips/${tripId}/budget?summary=true`
    );
  },

  /**
   * Update budget limit or active/closed status.
   */
  async updateBudget(
    tripId: string,
    payload: BudgetUpdateRequest
  ): Promise<BudgetResponse> {
    return apiClient.patch<BudgetResponse>(
      `/trips/${tripId}/budget`,
      payload
    );
  },

  /**
   * List paginated expenses for a trip budget.
   */
  async listExpenses(
    tripId: string,
    categoryId?: string,
    limit: number = 50,
    cursor?: string
  ): Promise<ExpenseListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (categoryId) params.set("category_id", categoryId);
    if (cursor) params.set("cursor", cursor);

    return apiClient.get<ExpenseListResponse>(
      `/trips/${tripId}/budget/expenses?${params.toString()}`
    );
  },

  /**
   * Add a new expense to the trip budget.
   */
  async addExpense(
    tripId: string,
    payload: ExpenseCreateRequest
  ): Promise<ExpenseResponse> {
    return apiClient.post<ExpenseResponse>(
      `/trips/${tripId}/budget/expenses`,
      payload
    );
  },

  /**
   * Update an existing expense.
   */
  async updateExpense(
    tripId: string,
    expenseId: string,
    payload: ExpenseUpdateRequest
  ): Promise<ExpenseResponse> {
    return apiClient.patch<ExpenseResponse>(
      `/trips/${tripId}/budget/expenses/${expenseId}`,
      payload
    );
  },

  /**
   * Delete an expense.
   */
  async deleteExpense(tripId: string, expenseId: string): Promise<void> {
    await apiClient.delete(`/trips/${tripId}/budget/expenses/${expenseId}`);
  },
};
