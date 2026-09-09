import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import {
  X,
  Compass,
  DollarSign,
  Check,
  AlertCircle,
  Calendar,
} from "lucide-react-native";
import { MediaItemResponse, ItineraryDayResponse, ExpenseResponse } from "@/core/api/types";
import { useItinerary } from "@/features/itinerary/hooks/use-itinerary";
import { useBudget } from "@/features/budget/hooks/use-budget";
import { Button } from "@/shared/components/ui/Button";

interface AttachMediaModalProps {
  visible: boolean;
  item: MediaItemResponse | null;
  mode: "activity" | "expense";
  tripId?: string;
  onClose: () => void;
  onAttachActivity: (mediaId: string, activityId: string) => Promise<any>;
  onAttachExpense: (mediaId: string, expenseId: string) => Promise<any>;
  isSubmitting?: boolean;
}

export const AttachMediaModal: React.FC<AttachMediaModalProps> = ({
  visible,
  item,
  mode,
  tripId,
  onClose,
  onAttachActivity,
  onAttachExpense,
  isSubmitting = false,
}) => {
  const { days } = useItinerary(tripId);
  const { expenses, budget } = useBudget(tripId);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!item) return null;

  const handleSubmit = async () => {
    if (!selectedId) {
      setError(`Please select a ${mode === "activity" ? "trip activity" : "budget expense"}.`);
      return;
    }

    setError(null);
    try {
      if (mode === "activity") {
        await onAttachActivity(item.media_id, selectedId);
      } else {
        await onAttachExpense(item.media_id, selectedId);
      }
      onClose();
    } catch (err: any) {
      setError(err?.message || `Failed to attach media to ${mode}.`);
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
        className="flex-1 justify-end bg-black/70"
      >
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl max-h-[80%] p-6">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800 mb-4">
            <View className="flex-row items-center">
              <View
                className={`w-8 h-8 rounded-lg items-center justify-center mr-2.5 ${
                  mode === "activity"
                    ? "bg-brand-600/20 border border-brand-500/30"
                    : "bg-emerald-500/20 border border-emerald-500/30"
                }`}
              >
                {mode === "activity" ? (
                  <Compass size={16} color="#818cf8" />
                ) : (
                  <DollarSign size={16} color="#34d399" />
                )}
              </View>
              <Text className="text-white text-lg font-bold">
                {mode === "activity" ? "Link to Activity" : "Link to Expense"}
              </Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Error Banner */}
          {error && (
            <View className="p-3 bg-rose-950/50 border border-rose-800/50 rounded-xl mb-4 flex-row items-center">
              <AlertCircle size={15} color="#f43f5e" />
              <Text className="text-rose-400 text-xs font-medium ml-2 flex-1">
                {error}
              </Text>
            </View>
          )}

          <Text className="text-slate-400 text-xs mb-3">
            Select target {mode === "activity" ? "itinerary stop" : "expense entry"} to attach this file to:
          </Text>

          {/* Selection List */}
          <ScrollView className="max-h-72 mb-5" showsVerticalScrollIndicator={false}>
            {mode === "activity" ? (
              days.length === 0 ? (
                <View className="p-6 bg-slate-950 border border-slate-800 rounded-xl items-center">
                  <Text className="text-slate-400 text-xs text-center">
                    No itinerary days or activities found. Create days in your itinerary first.
                  </Text>
                </View>
              ) : (
                days.map((day: ItineraryDayResponse) => (
                  <View key={day.day_id} className="mb-3">
                    <Text className="text-slate-400 text-[11px] font-semibold uppercase mb-1.5 px-1">
                      Day {day.day_number} {day.title ? `— ${day.title}` : ""}
                    </Text>
                    {day.items && day.items.length > 0 ? (
                      day.items.map((act) => {
                        const isSelected = selectedId === act.item_id;
                        return (
                          <TouchableOpacity
                            key={act.item_id}
                            onPress={() => setSelectedId(act.item_id)}
                            className={`p-3 rounded-xl border mb-1.5 flex-row items-center justify-between ${
                              isSelected
                                ? "bg-brand-600/20 border-brand-500"
                                : "bg-slate-950 border-slate-800"
                            }`}
                          >
                            <View className="flex-1 mr-2">
                              <Text
                                className={`text-xs font-bold ${
                                  isSelected ? "text-brand-300" : "text-white"
                                }`}
                              >
                                {act.title}
                              </Text>
                              <Text className="text-slate-400 text-[10px] capitalize">
                                {act.item_type}
                              </Text>
                            </View>
                            {isSelected && <Check size={16} color="#818cf8" />}
                          </TouchableOpacity>
                        );
                      })
                    ) : (
                      <Text className="text-slate-500 text-xs italic px-1 mb-1">
                        No activities on this day.
                      </Text>
                    )}
                  </View>
                ))
              )
            ) : expenses.length === 0 ? (
              <View className="p-6 bg-slate-950 border border-slate-800 rounded-xl items-center">
                <Text className="text-slate-400 text-xs text-center">
                  No budget expenses found. Log an expense in your budget first.
                </Text>
              </View>
            ) : (
              expenses.map((exp: ExpenseResponse) => {
                const isSelected = selectedId === exp.expense_id;
                return (
                  <TouchableOpacity
                    key={exp.expense_id}
                    onPress={() => setSelectedId(exp.expense_id)}
                    className={`p-3 rounded-xl border mb-2 flex-row items-center justify-between ${
                      isSelected
                        ? "bg-emerald-500/20 border-emerald-500"
                        : "bg-slate-950 border-slate-800"
                    }`}
                  >
                    <View className="flex-1 mr-2">
                      <Text
                        className={`text-xs font-bold ${
                          isSelected ? "text-emerald-300" : "text-white"
                        }`}
                      >
                        {exp.title}
                      </Text>
                      <Text className="text-slate-400 text-[10px]">
                        {exp.amount} {exp.currency} • {exp.expense_type}
                      </Text>
                    </View>
                    {isSelected && <Check size={16} color="#34d399" />}
                  </TouchableOpacity>
                );
              })
            )}
          </ScrollView>

          {/* Submit */}
          <Button
            label={`Attach to ${mode === "activity" ? "Activity" : "Expense"}`}
            onPress={handleSubmit}
            isLoading={isSubmitting}
            disabled={!selectedId}
            className="w-full"
          />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
