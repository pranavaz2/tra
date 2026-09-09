/**
 * useBudget Hook.
 *
 * Manages trip budget, spending breakdowns, expenses, and mutations.
 */

import { useState, useEffect, useCallback } from "react";
import { BudgetApi } from "../api/budget-api";
import {
  BudgetSummaryResponse,
  BudgetResponse,
  BudgetCreateRequest,
  BudgetUpdateRequest,
  ExpenseResponse,
  ExpenseCreateRequest,
  ExpenseUpdateRequest,
} from "@/core/api/types";
import { TravixApiError } from "@/core/api/client";

export function useBudget(tripId?: string) {
  const [budgetSummary, setBudgetSummary] = useState<BudgetSummaryResponse | null>(null);
  const [expenses, setExpenses] = useState<ExpenseResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBudgetAndExpenses = useCallback(async () => {
    if (!tripId) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      try {
        const summaryData = await BudgetApi.getBudgetSummary(tripId);
        setBudgetSummary(summaryData);

        // Also fetch expenses
        const expenseData = await BudgetApi.listExpenses(tripId);
        setExpenses(expenseData.items || []);
      } catch (err: any) {
        if (err instanceof TravixApiError && err.status === 404) {
          // No budget created yet for this trip
          setBudgetSummary(null);
          setExpenses([]);
        } else if (err instanceof TravixApiError) {
          setError(err.message);
        } else {
          setError("Failed to load budget details.");
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [tripId]);

  useEffect(() => {
    fetchBudgetAndExpenses();
  }, [fetchBudgetAndExpenses]);

  const createBudget = async (
    payload: BudgetCreateRequest
  ): Promise<BudgetResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const created = await BudgetApi.createBudget(tripId, payload);
      await fetchBudgetAndExpenses();
      return created;
    } catch (err: any) {
      const msg = err instanceof TravixApiError ? err.message : "Failed to create budget.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const updateBudget = async (
    payload: BudgetUpdateRequest
  ): Promise<BudgetResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const updated = await BudgetApi.updateBudget(tripId, payload);
      await fetchBudgetAndExpenses();
      return updated;
    } catch (err: any) {
      const msg = err instanceof TravixApiError ? err.message : "Failed to update budget.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const addExpense = async (
    payload: ExpenseCreateRequest
  ): Promise<ExpenseResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const added = await BudgetApi.addExpense(tripId, payload);
      await fetchBudgetAndExpenses();
      return added;
    } catch (err: any) {
      const msg = err instanceof TravixApiError ? err.message : "Failed to record expense.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const updateExpense = async (
    expenseId: string,
    payload: ExpenseUpdateRequest
  ): Promise<ExpenseResponse> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      const updated = await BudgetApi.updateExpense(tripId, expenseId, payload);
      await fetchBudgetAndExpenses();
      return updated;
    } catch (err: any) {
      const msg = err instanceof TravixApiError ? err.message : "Failed to update expense.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  const deleteExpense = async (expenseId: string): Promise<void> => {
    if (!tripId) throw new Error("Trip ID is required");
    setIsMutating(true);
    setError(null);
    try {
      await BudgetApi.deleteExpense(tripId, expenseId);
      await fetchBudgetAndExpenses();
    } catch (err: any) {
      const msg = err instanceof TravixApiError ? err.message : "Failed to delete expense.";
      setError(msg);
      throw err;
    } finally {
      setIsMutating(false);
    }
  };

  return {
    budgetSummary,
    budget: budgetSummary?.budget || null,
    hasBudget: !!budgetSummary?.budget,
    expenses,
    isLoading,
    isMutating,
    error,
    refresh: fetchBudgetAndExpenses,
    createBudget,
    updateBudget,
    addExpense,
    updateExpense,
    deleteExpense,
  };
}
