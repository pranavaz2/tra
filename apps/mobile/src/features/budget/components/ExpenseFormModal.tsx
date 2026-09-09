import React, { useState, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { X, Calendar, DollarSign, Tag, FileText } from "lucide-react-native";
import {
  CategoryResponse,
  ExpenseCreateRequest,
  ExpenseResponse,
  ExpenseType,
  ExpenseUpdateRequest,
} from "@/core/api/types";
import { Button } from "@/shared/components/ui/Button";

interface ExpenseFormModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (data: ExpenseCreateRequest | ExpenseUpdateRequest) => Promise<void>;
  initialExpense?: ExpenseResponse | null;
  categories: CategoryResponse[];
  currency: string;
  isSubmitting?: boolean;
}

const EXPENSE_TYPES: { label: string; value: ExpenseType }[] = [
  { label: "Activity", value: "activity" },
  { label: "Transport", value: "transport" },
  { label: "Lodging", value: "lodging" },
  { label: "Restaurant", value: "restaurant" },
  { label: "Other", value: "other" },
];

export const ExpenseFormModal: React.FC<ExpenseFormModalProps> = ({
  visible,
  onClose,
  onSubmit,
  initialExpense,
  categories,
  currency,
  isSubmitting = false,
}) => {
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [expenseType, setExpenseType] = useState<ExpenseType>("activity");
  const [categoryId, setCategoryId] = useState("");
  const [expenseDate, setExpenseDate] = useState("");
  const [description, setDescription] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      if (initialExpense) {
        setTitle(initialExpense.title);
        setAmount(String(initialExpense.amount));
        setExpenseType(initialExpense.expense_type);
        setCategoryId(initialExpense.category_id);
        setExpenseDate(initialExpense.expense_date);
        setDescription(initialExpense.description || "");
      } else {
        setTitle("");
        setAmount("");
        setExpenseType("activity");
        // Default category matching expense type if found, or first category
        const defaultCat =
          categories.find(
            (c) => c.name.toLowerCase() === "activity"
          ) || categories[0];
        setCategoryId(defaultCat ? defaultCat.category_id : "");
        setExpenseDate(new Date().toISOString().split("T")[0]);
        setDescription("");
      }
      setValidationError(null);
    }
  }, [visible, initialExpense, categories]);

  // When expense type changes, if creating new expense, attempt smart match category
  const handleTypeChange = (type: ExpenseType) => {
    setExpenseType(type);
    if (!initialExpense) {
      const match = categories.find((c) => {
        const catName = c.name.toLowerCase();
        if (type === "restaurant" && catName.includes("food")) return true;
        return catName.includes(type);
      });
      if (match) {
        setCategoryId(match.category_id);
      }
    }
  };

  const handleSubmit = async () => {
    setValidationError(null);

    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setValidationError("Please enter an expense title.");
      return;
    }
    if (trimmedTitle.length > 100) {
      setValidationError("Title must be 100 characters or fewer.");
      return;
    }

    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setValidationError("Please enter a valid amount greater than 0.");
      return;
    }

    if (!categoryId) {
      setValidationError("Please select an expense category.");
      return;
    }

    if (!expenseDate.trim().match(/^\d{4}-\d{2}-\d{2}$/)) {
      setValidationError("Please enter a valid date in YYYY-MM-DD format.");
      return;
    }

    try {
      if (initialExpense) {
        const payload: ExpenseUpdateRequest = {
          title: trimmedTitle,
          amount: parsedAmount,
          expense_type: expenseType,
          category_id: categoryId,
          expense_date: expenseDate.trim(),
          description: description.trim() || undefined,
        };
        await onSubmit(payload);
      } else {
        const payload: ExpenseCreateRequest = {
          title: trimmedTitle,
          amount: parsedAmount,
          expense_type: expenseType,
          category_id: categoryId,
          expense_date: expenseDate.trim(),
          description: description.trim() || undefined,
        };
        await onSubmit(payload);
      }
    } catch (err: any) {
      setValidationError(err.message || "Failed to save expense.");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1 justify-end bg-black/60"
      >
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl max-h-[90%] p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800">
            <Text className="text-white text-xl font-bold">
              {initialExpense ? "Edit Expense" : "Add Expense"}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          <ScrollView
            showsVerticalScrollIndicator={false}
            className="mt-4"
            contentContainerStyle={{ paddingBottom: 24 }}
          >
            {validationError && (
              <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4">
                <Text className="text-rose-400 text-xs font-medium">
                  {validationError}
                </Text>
              </View>
            )}

            {/* Title */}
            <View className="mb-4">
              <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                Title *
              </Text>
              <TextInput
                value={title}
                onChangeText={setTitle}
                placeholder="e.g., Dinner at Osteria, Train ticket"
                placeholderTextColor="#64748b"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm"
              />
            </View>

            {/* Amount & Date */}
            <View className="flex-row gap-3 mb-4">
              <View className="flex-1">
                <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                  Amount ({currency}) *
                </Text>
                <View className="flex-row items-center bg-slate-800 border border-slate-700 rounded-xl px-3 py-1">
                  <DollarSign size={16} color="#94a3b8" />
                  <TextInput
                    value={amount}
                    onChangeText={setAmount}
                    placeholder="0.00"
                    placeholderTextColor="#64748b"
                    keyboardType="numeric"
                    className="flex-1 ml-1 py-2 text-white text-sm font-semibold"
                  />
                </View>
              </View>

              <View className="flex-1">
                <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                  Date (YYYY-MM-DD) *
                </Text>
                <View className="flex-row items-center bg-slate-800 border border-slate-700 rounded-xl px-3 py-1">
                  <Calendar size={16} color="#94a3b8" />
                  <TextInput
                    value={expenseDate}
                    onChangeText={setExpenseDate}
                    placeholder="2026-09-05"
                    placeholderTextColor="#64748b"
                    className="flex-1 ml-1 py-2 text-white text-sm"
                  />
                </View>
              </View>
            </View>

            {/* Expense Type */}
            <View className="mb-4">
              <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                Expense Type *
              </Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row gap-2 py-1">
                {EXPENSE_TYPES.map((type) => {
                  const isSelected = expenseType === type.value;
                  return (
                    <TouchableOpacity
                      key={type.value}
                      onPress={() => handleTypeChange(type.value)}
                      className={`px-3 py-2 rounded-xl border mr-2 ${
                        isSelected
                          ? "bg-brand-600 border-brand-500"
                          : "bg-slate-800 border-slate-700"
                      }`}
                    >
                      <Text
                        className={`text-xs font-semibold ${
                          isSelected ? "text-white" : "text-slate-300"
                        }`}
                      >
                        {type.label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            </View>

            {/* Category */}
            {categories.length > 0 && (
              <View className="mb-4">
                <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                  Budget Category *
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row gap-2 py-1">
                  {categories.map((cat) => {
                    const isSelected = categoryId === cat.category_id;
                    return (
                      <TouchableOpacity
                        key={cat.category_id}
                        onPress={() => setCategoryId(cat.category_id)}
                        className={`px-3 py-2 rounded-xl border mr-2 flex-row items-center ${
                          isSelected
                            ? "bg-emerald-600 border-emerald-500"
                            : "bg-slate-800 border-slate-700"
                        }`}
                      >
                        <Tag size={12} color={isSelected ? "#ffffff" : "#94a3b8"} />
                        <Text
                          className={`text-xs font-semibold ml-1.5 ${
                            isSelected ? "text-white" : "text-slate-300"
                          }`}
                        >
                          {cat.name}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </View>
            )}

            {/* Description / Notes */}
            <View className="mb-6">
              <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                Notes (Optional)
              </Text>
              <TextInput
                value={description}
                onChangeText={setDescription}
                placeholder="Add receipt notes, payment method, etc."
                placeholderTextColor="#64748b"
                multiline
                numberOfLines={3}
                textAlignVertical="top"
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm"
              />
            </View>

            {/* Submit Button */}
            <Button
              label={initialExpense ? "Save Changes" : "Add Expense"}
              onPress={handleSubmit}
              isLoading={isSubmitting}
              className="w-full"
            />
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
