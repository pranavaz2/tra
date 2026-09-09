import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ArrowLeft,
  DollarSign,
  Plus,
  SlidersHorizontal,
  PieChart,
  Receipt,
  TrendingDown,
  Sparkles,
} from "lucide-react-native";
import { useBudget } from "@/features/budget/hooks/use-budget";
import { useCollaboration } from "@/features/collaboration/hooks/use-collaboration";
import { useTripRealtime } from "@/core/realtime/use-trip-realtime";
import { TripLivePresenceBar } from "@/features/collaboration/components/TripLivePresenceBar";
import { useTripWarnings } from "@/features/assistant/hooks/use-trip-warnings";
import { TravelWarningBanner } from "@/features/assistant/components/TravelWarningBanner";
import { BudgetProgressBar } from "@/features/budget/components/BudgetProgressBar";
import { ExpenseCard } from "@/features/budget/components/ExpenseCard";
import { BudgetLimitModal } from "@/features/budget/components/BudgetLimitModal";
import { ExpenseFormModal } from "@/features/budget/components/ExpenseFormModal";
import { Card } from "@/shared/components/ui/Card";
import { Button } from "@/shared/components/ui/Button";
import { ErrorMessage } from "@/shared/components/feedback/ErrorMessage";
import { LoadingScreen } from "@/shared/components/feedback/LoadingScreen";
import {
  BudgetStatus,
  ExpenseCreateRequest,
  ExpenseResponse,
  ExpenseUpdateRequest,
} from "@/core/api/types";

export default function TripBudgetScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();

  const {
    budgetSummary,
    budget,
    hasBudget,
    expenses,
    isLoading,
    isMutating,
    error,
    refresh,
    createBudget,
    updateBudget,
    addExpense,
    updateExpense,
    deleteExpense,
  } = useBudget(id);

  const { isViewer, isOwner } = useCollaboration(id);
  const { budgetWarnings, dismissWarning } = useTripWarnings(id);
  const { collaborators, connectionStatus } = useTripRealtime(id);

  // Modal States
  const [isBudgetModalVisible, setIsBudgetModalVisible] = useState(false);
  const [isExpenseModalVisible, setIsExpenseModalVisible] = useState(false);
  const [editingExpense, setEditingExpense] = useState<ExpenseResponse | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  };

  // Handlers
  const handleOpenCreateBudget = () => {
    setActionError(null);
    setIsBudgetModalVisible(true);
  };

  const handleOpenEditBudget = () => {
    setActionError(null);
    setIsBudgetModalVisible(true);
  };

  const handleSaveBudget = async (
    limitAmount: number,
    currency?: string,
    status?: BudgetStatus
  ) => {
    setActionError(null);
    if (hasBudget) {
      await updateBudget({
        limit_amount: limitAmount,
        status: status || "active",
      });
    } else {
      await createBudget({
        limit_amount: limitAmount,
        currency: currency || "USD",
      });
    }
    setIsBudgetModalVisible(false);
  };

  const handleOpenAddExpense = () => {
    setActionError(null);
    setEditingExpense(null);
    setIsExpenseModalVisible(true);
  };

  const handleOpenEditExpense = (expense: ExpenseResponse) => {
    setActionError(null);
    setEditingExpense(expense);
    setIsExpenseModalVisible(true);
  };

  const handleSaveExpense = async (
    data: ExpenseCreateRequest | ExpenseUpdateRequest
  ) => {
    setActionError(null);
    if (editingExpense) {
      await updateExpense(editingExpense.expense_id, data as ExpenseUpdateRequest);
    } else {
      await addExpense(data as ExpenseCreateRequest);
    }
    setIsExpenseModalVisible(false);
    setEditingExpense(null);
  };

  const handleDeleteExpense = async (expenseId: string) => {
    setActionError(null);
    try {
      await deleteExpense(expenseId);
    } catch (err: any) {
      setActionError(err.message || "Failed to delete expense.");
    }
  };

  if (isLoading && !refreshing) {
    return <LoadingScreen message="Loading trip budget..." />;
  }

  const categories = budget?.categories || [];
  const categoryMap = new Map(categories.map((c) => [c.category_id, c.name]));

  return (
    <SafeAreaView className="flex-1 bg-slate-950" edges={["top", "bottom"]}>
      {/* Top App Bar */}
      <View className="flex-row items-center justify-between px-5 py-3 border-b border-slate-800/80 bg-slate-950">
        <TouchableOpacity
          onPress={() => router.back()}
          className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 items-center justify-center active:bg-slate-800"
          accessibilityLabel="Back to Trip"
        >
          <ArrowLeft size={18} color="#ffffff" />
        </TouchableOpacity>

        <Text className="text-white text-lg font-bold">Trip Budget</Text>

        {hasBudget && !isViewer ? (
          <TouchableOpacity
            onPress={handleOpenAddExpense}
            className="w-10 h-10 rounded-full bg-brand-600 border border-brand-500 items-center justify-center active:bg-brand-700"
            accessibilityLabel="Add Expense"
          >
            <Plus size={20} color="#ffffff" />
          </TouchableOpacity>
        ) : (
          <View className="w-10" />
        )}
      </View>

      {/* Live Presence Bar */}
      <TripLivePresenceBar
        collaborators={collaborators}
        connectionStatus={connectionStatus}
      />

      <ScrollView
        className="flex-1"
        contentContainerStyle={{ padding: 20 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#6366f1"
            colors={["#6366f1"]}
          />
        }
      >
        {/* Error Banners */}
        {error && <ErrorMessage message={error} className="mb-4" />}
        {actionError && <ErrorMessage message={actionError} className="mb-4" />}

        {/* Proactive Budget Warnings */}
        {budgetWarnings.length > 0 && (
          <View className="mb-4">
            <TravelWarningBanner
              warnings={budgetWarnings}
              onDismiss={dismissWarning}
            />
          </View>
        )}

        {!hasBudget ? (
          /* Empty Budget State */
          <Card className="p-8 bg-slate-900/80 border border-emerald-500/30 items-center text-center mt-6">
            <View className="w-16 h-16 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 items-center justify-center mb-4">
              <DollarSign size={32} color="#10b981" />
            </View>
            <Text className="text-white text-xl font-bold mb-2">
              Track Your Trip Expenses
            </Text>
            <Text className="text-slate-300 text-sm text-center mb-6 leading-relaxed">
              Set a spending target to log dining, tickets, transit, and lodging. Travix monitors your pace and alerts you before overspending.
            </Text>
            <Button
              label="Set Up Budget Target"
              variant="primary"
              size="lg"
              icon={<DollarSign size={18} color="#ffffff" />}
              onPress={handleOpenCreateBudget}
              className="w-full"
            />
          </Card>
        ) : (
          /* Active Budget Dashboard */
          <>
            {/* Overview Summary Card */}
            <Card className="p-5 bg-slate-900 border border-slate-800 mb-6">
              <View className="flex-row items-center justify-between mb-4">
                <View className="flex-row items-center">
                  <View className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 items-center justify-center mr-3">
                    <DollarSign size={20} color="#10b981" />
                  </View>
                  <View>
                    <Text className="text-slate-400 text-xs font-semibold uppercase">
                      Budget Status
                    </Text>
                    <Text className="text-white text-sm font-bold capitalize">
                      {budget?.status || "Active"}
                    </Text>
                  </View>
                </View>

                {isOwner && (
                  <TouchableOpacity
                    onPress={handleOpenEditBudget}
                    className="flex-row items-center px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 active:bg-slate-700"
                  >
                    <SlidersHorizontal size={13} color="#94a3b8" />
                    <Text className="text-slate-300 text-xs font-medium ml-1.5">
                      Edit Limit
                    </Text>
                  </TouchableOpacity>
                )}
              </View>

              {/* Numbers Grid */}
              <View className="flex-row items-baseline justify-between mb-4 pt-2 border-t border-slate-800">
                <View>
                  <Text className="text-slate-400 text-xs font-semibold mb-1">
                    Total Budget
                  </Text>
                  <Text className="text-white text-2xl font-bold">
                    {Number(budget?.limit ?? budget?.limit_amount ?? 0).toFixed(2)}{" "}
                    <Text className="text-xs font-semibold text-slate-400">
                      {budget?.currency}
                    </Text>
                  </Text>
                </View>

                <View className="items-center">
                  <Text className="text-slate-400 text-xs font-semibold mb-1">
                    Spent
                  </Text>
                  <Text className="text-emerald-400 text-xl font-bold">
                    {Number(budget?.total_spent || 0).toFixed(2)}
                  </Text>
                </View>

                <View className="items-end">
                  <Text className="text-slate-400 text-xs font-semibold mb-1">
                    Remaining
                  </Text>
                  <Text
                    className={`text-xl font-bold ${
                      (budget?.remaining || 0) < 0
                        ? "text-rose-400"
                        : "text-slate-200"
                    }`}
                  >
                    {Number(budget?.remaining || 0).toFixed(2)}
                  </Text>
                </View>
              </View>

              {/* Progress Track */}
              <BudgetProgressBar
                spentPercentage={budget?.spent_percentage || 0}
                totalSpent={budget?.total_spent || 0}
                limit={budget?.limit ?? budget?.limit_amount ?? 0}
                currency={budget?.currency || "USD"}
              />
            </Card>

            {/* Category Breakdown Card (if spending exists) */}
            {budgetSummary?.type_breakdowns &&
              Object.keys(budgetSummary.type_breakdowns).length > 0 && (
                <Card className="p-5 bg-slate-900 border border-slate-800 mb-6">
                  <View className="flex-row items-center mb-3">
                    <PieChart size={16} color="#818cf8" />
                    <Text className="text-white text-sm font-bold ml-2">
                      Spending by Category
                    </Text>
                  </View>

                  <View className="space-y-2.5">
                    {Object.entries(budgetSummary.type_breakdowns).map(
                      ([type, amount]) => {
                        const total = Number(budget?.total_spent) || 1;
                        const pct = Math.round((Number(amount) / total) * 100);
                        return (
                          <View key={type} className="mb-2">
                            <View className="flex-row items-center justify-between mb-1">
                              <Text className="text-slate-300 text-xs font-medium capitalize">
                                {type}
                              </Text>
                              <Text className="text-white text-xs font-semibold">
                                {Number(amount).toFixed(2)} {budget?.currency}{" "}
                                <Text className="text-slate-500 font-normal">
                                  ({pct}%)
                                </Text>
                              </Text>
                            </View>
                            <View className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                              <View
                                className="h-full bg-brand-500 rounded-full"
                                style={{ width: `${Math.min(pct, 100)}%` }}
                              />
                            </View>
                          </View>
                        );
                      }
                    )}
                  </View>
                </Card>
              )}

            {/* Expenses List Section */}
            <View className="flex-row items-center justify-between mb-3">
              <View className="flex-row items-center">
                <Receipt size={16} color="#94a3b8" />
                <Text className="text-slate-300 text-xs font-semibold uppercase tracking-wider ml-2">
                  Expenses ({expenses.length})
                </Text>
              </View>

              {!isViewer && (
                <TouchableOpacity
                  onPress={handleOpenAddExpense}
                  className="flex-row items-center px-2.5 py-1 rounded-lg bg-brand-600/20 border border-brand-500/30 active:bg-brand-600/30"
                >
                  <Plus size={13} color="#818cf8" />
                  <Text className="text-brand-300 text-xs font-semibold ml-1">
                    Add
                  </Text>
                </TouchableOpacity>
              )}
            </View>

            {expenses.length === 0 ? (
              <Card className="p-6 bg-slate-900/60 border border-dashed border-slate-800 items-center justify-center">
                <Text className="text-slate-400 text-sm font-medium mb-1">
                  No expenses logged yet
                </Text>
                <Text className="text-slate-500 text-xs text-center mb-4">
                  Keep track of flights, hotels, food, and activities.
                </Text>
                {!isViewer && (
                  <Button
                    label="Add First Expense"
                    onPress={handleOpenAddExpense}
                    variant="secondary"
                    size="sm"
                  />
                )}
              </Card>
            ) : (
              <View>
                {expenses.map((expense) => (
                  <ExpenseCard
                    key={expense.expense_id}
                    expense={expense}
                    categoryName={categoryMap.get(expense.category_id)}
                    onEdit={handleOpenEditExpense}
                    onDelete={handleDeleteExpense}
                    isDeleting={isMutating}
                    canManage={!isViewer}
                  />
                ))}
              </View>
            )}
          </>
        )}
      </ScrollView>

      {/* Budget Limit Modal */}
      <BudgetLimitModal
        visible={isBudgetModalVisible}
        onClose={() => setIsBudgetModalVisible(false)}
        onSubmit={handleSaveBudget}
        currentLimit={budget?.limit ?? budget?.limit_amount}
        currentCurrency={budget?.currency}
        currentStatus={budget?.status}
        isCreating={!hasBudget}
        isSubmitting={isMutating}
      />

      {/* Expense Form Modal */}
      <ExpenseFormModal
        visible={isExpenseModalVisible}
        onClose={() => {
          setIsExpenseModalVisible(false);
          setEditingExpense(null);
        }}
        onSubmit={handleSaveExpense}
        initialExpense={editingExpense}
        categories={categories}
        currency={budget?.currency || "USD"}
        isSubmitting={isMutating}
      />
    </SafeAreaView>
  );
}
