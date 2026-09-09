import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import {
  Compass,
  Car,
  Home,
  Utensils,
  Receipt,
  Edit2,
  Trash2,
} from "lucide-react-native";
import { ExpenseResponse, ExpenseType } from "@/core/api/types";
import { Card } from "@/shared/components/ui/Card";

interface ExpenseCardProps {
  expense: ExpenseResponse;
  categoryName?: string;
  onEdit: (expense: ExpenseResponse) => void;
  onDelete: (expenseId: string) => void;
  isDeleting?: boolean;
  canManage?: boolean;
}

const getExpenseIcon = (type: ExpenseType) => {
  switch (type) {
    case "activity":
      return <Compass size={18} color="#10b981" />;
    case "transport":
      return <Car size={18} color="#38bdf8" />;
    case "lodging":
      return <Home size={18} color="#fbbf24" />;
    case "restaurant":
      return <Utensils size={18} color="#f43f5e" />;
    case "other":
    default:
      return <Receipt size={18} color="#a78bfa" />;
  }
};

const getExpenseBadgeStyle = (type: ExpenseType) => {
  switch (type) {
    case "activity":
      return "bg-emerald-950/40 border-emerald-800/40 text-emerald-400";
    case "transport":
      return "bg-sky-950/40 border-sky-800/40 text-sky-400";
    case "lodging":
      return "bg-amber-950/40 border-amber-800/40 text-amber-400";
    case "restaurant":
      return "bg-rose-950/40 border-rose-800/40 text-rose-400";
    case "other":
    default:
      return "bg-purple-950/40 border-purple-800/40 text-purple-400";
  }
};

export const ExpenseCard: React.FC<ExpenseCardProps> = ({
  expense,
  categoryName,
  onEdit,
  onDelete,
  isDeleting = false,
  canManage = true,
}) => {
  const handleDelete = () => {
    Alert.alert(
      "Delete Expense",
      `Are you sure you want to remove "${expense.title}"?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => onDelete(expense.expense_id),
        },
      ]
    );
  };

  const badgeStyle = getExpenseBadgeStyle(expense.expense_type);

  return (
    <Card className="p-4 bg-slate-900 border border-slate-800 mb-3">
      <View className="flex-row items-start justify-between">
        {/* Left: Icon & details */}
        <View className="flex-row items-start flex-1 mr-2">
          <View className="w-10 h-10 rounded-xl bg-slate-800 border border-slate-700/60 items-center justify-center mr-3 mt-0.5">
            {getExpenseIcon(expense.expense_type)}
          </View>
          <View className="flex-1">
            <Text className="text-white font-semibold text-base" numberOfLines={1}>
              {expense.title}
            </Text>
            
            <View className="flex-row items-center flex-wrap gap-1.5 mt-1">
              <View className={`px-2 py-0.5 rounded-full border ${badgeStyle}`}>
                <Text className="text-[11px] font-medium capitalize">
                  {expense.expense_type}
                </Text>
              </View>
              {categoryName && (
                <View className="px-2 py-0.5 rounded-full border bg-slate-800 border-slate-700">
                  <Text className="text-slate-300 text-[11px] font-medium">
                    {categoryName}
                  </Text>
                </View>
              )}
              <Text className="text-slate-400 text-xs ml-1">
                {expense.expense_date}
              </Text>
            </View>

            {expense.description ? (
              <Text className="text-slate-400 text-xs mt-2" numberOfLines={2}>
                {expense.description}
              </Text>
            ) : null}
          </View>
        </View>

        {/* Right: Amount & actions */}
        <View className="items-end">
          <Text className="text-white font-bold text-base">
            {Number(expense.amount).toFixed(2)}{" "}
            <Text className="text-xs font-semibold text-slate-400">
              {expense.currency}
            </Text>
          </Text>

          {canManage && (
            <View className="flex-row items-center mt-3 gap-2">
              <TouchableOpacity
                onPress={() => onEdit(expense)}
                disabled={isDeleting}
                className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 active:bg-slate-700"
                accessibilityLabel="Edit expense"
              >
                <Edit2 size={14} color="#94a3b8" />
              </TouchableOpacity>

              <TouchableOpacity
                onPress={handleDelete}
                disabled={isDeleting}
                className="p-1.5 rounded-lg bg-rose-950/40 border border-rose-800/40 active:bg-rose-900/40"
                accessibilityLabel="Delete expense"
              >
                <Trash2 size={14} color="#f43f5e" />
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>
    </Card>
  );
};
