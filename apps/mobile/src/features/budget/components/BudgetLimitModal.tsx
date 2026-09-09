import React, { useState, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { X, DollarSign, Check } from "lucide-react-native";
import { BudgetStatus } from "@/core/api/types";
import { Button } from "@/shared/components/ui/Button";

interface BudgetLimitModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (
    limitAmount: number,
    currency?: string,
    status?: BudgetStatus
  ) => Promise<void>;
  currentLimit?: number;
  currentCurrency?: string;
  currentStatus?: BudgetStatus;
  isCreating: boolean;
  isSubmitting?: boolean;
}

const COMMON_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "INR"];

export const BudgetLimitModal: React.FC<BudgetLimitModalProps> = ({
  visible,
  onClose,
  onSubmit,
  currentLimit,
  currentCurrency = "USD",
  currentStatus = "active",
  isCreating,
  isSubmitting = false,
}) => {
  const [limit, setLimit] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [status, setStatus] = useState<BudgetStatus>("active");
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      setLimit(currentLimit ? String(currentLimit) : "");
      setCurrency(currentCurrency || "USD");
      setStatus(currentStatus || "active");
      setValidationError(null);
    }
  }, [visible, currentLimit, currentCurrency, currentStatus]);

  const handleSubmit = async () => {
    setValidationError(null);

    const parsedLimit = parseFloat(limit);
    if (isNaN(parsedLimit) || parsedLimit <= 0) {
      setValidationError("Please enter a valid budget limit greater than 0.");
      return;
    }

    const trimmedCurrency = currency.trim().toUpperCase();
    if (isCreating && trimmedCurrency.length !== 3) {
      setValidationError("Currency code must be exactly 3 uppercase letters (e.g., USD, EUR).");
      return;
    }

    try {
      await onSubmit(parsedLimit, trimmedCurrency, status);
    } catch (err: any) {
      setValidationError(err.message || "Failed to save budget.");
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
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <Text className="text-white text-xl font-bold">
              {isCreating ? "Set Trip Budget" : "Edit Budget Limit"}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {validationError && (
            <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4">
              <Text className="text-rose-400 text-xs font-medium">
                {validationError}
              </Text>
            </View>
          )}

          {/* Budget Limit Input */}
          <View className="mb-4">
            <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
              Total Budget Limit *
            </Text>
            <View className="flex-row items-center bg-slate-800 border border-slate-700 rounded-xl px-3 py-1">
              <DollarSign size={18} color="#94a3b8" />
              <TextInput
                value={limit}
                onChangeText={setLimit}
                placeholder="e.g., 2500.00"
                placeholderTextColor="#64748b"
                keyboardType="numeric"
                className="flex-1 ml-1 py-3 text-white text-base font-semibold"
              />
            </View>
          </View>

          {/* Currency Selection (only on creation or informational) */}
          {isCreating ? (
            <View className="mb-4">
              <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                Currency Code (3 letters) *
              </Text>
              <View className="flex-row flex-wrap gap-2 mb-2">
                {COMMON_CURRENCIES.map((curr) => {
                  const isSelected = currency === curr;
                  return (
                    <TouchableOpacity
                      key={curr}
                      onPress={() => setCurrency(curr)}
                      className={`px-3 py-1.5 rounded-lg border ${
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
                        {curr}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <TextInput
                value={currency}
                onChangeText={(text) => setCurrency(text.toUpperCase().slice(0, 3))}
                placeholder="Other currency (e.g. SEK)"
                placeholderTextColor="#64748b"
                autoCapitalize="characters"
                maxLength={3}
                className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2 text-white text-sm"
              />
            </View>
          ) : (
            <View className="mb-4">
              <Text className="text-slate-300 text-xs font-semibold uppercase mb-1.5">
                Budget Status
              </Text>
              <View className="flex-row gap-3">
                <TouchableOpacity
                  onPress={() => setStatus("active")}
                  className={`flex-1 py-2.5 px-3 rounded-xl border flex-row items-center justify-center ${
                    status === "active"
                      ? "bg-emerald-600 border-emerald-500"
                      : "bg-slate-800 border-slate-700"
                  }`}
                >
                  {status === "active" && <Check size={14} color="#ffffff" className="mr-1.5" />}
                  <Text
                    className={`text-xs font-semibold ${
                      status === "active" ? "text-white" : "text-slate-300"
                    }`}
                  >
                    Active
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  onPress={() => setStatus("closed")}
                  className={`flex-1 py-2.5 px-3 rounded-xl border flex-row items-center justify-center ${
                    status === "closed"
                      ? "bg-slate-700 border-slate-600"
                      : "bg-slate-800 border-slate-700"
                  }`}
                >
                  {status === "closed" && <Check size={14} color="#ffffff" className="mr-1.5" />}
                  <Text
                    className={`text-xs font-semibold ${
                      status === "closed" ? "text-white" : "text-slate-300"
                    }`}
                  >
                    Closed
                  </Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Submit */}
          <Button
            label={isCreating ? "Create Budget" : "Update Budget"}
            onPress={handleSubmit}
            isLoading={isSubmitting}
            className="w-full mt-2"
          />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
