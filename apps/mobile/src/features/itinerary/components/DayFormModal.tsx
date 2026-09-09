import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  Modal,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { X, Calendar, AlertCircle } from "lucide-react-native";
import {
  ItineraryDayCreateRequest,
  ItineraryDayResponse,
} from "@/core/api/types";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";

interface DayFormModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (data: ItineraryDayCreateRequest) => Promise<void>;
  initialDay?: ItineraryDayResponse | null;
  suggestedDayNumber: number;
  isSubmitting?: boolean;
}

export const DayFormModal: React.FC<DayFormModalProps> = ({
  visible,
  onClose,
  onSubmit,
  initialDay,
  suggestedDayNumber,
  isSubmitting = false,
}) => {
  const isEditing = !!initialDay;

  const [dayNumber, setDayNumber] = useState(String(suggestedDayNumber));
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      if (initialDay) {
        setDayNumber(String(initialDay.day_number));
        setTitle(initialDay.title || "");
        setDate(initialDay.date || "");
      } else {
        setDayNumber(String(suggestedDayNumber));
        setTitle("");
        setDate("");
      }
      setErrors({});
      setServerError(null);
    }
  }, [visible, initialDay, suggestedDayNumber]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    const parsedDayNumber = parseInt(dayNumber.trim(), 10);
    if (isNaN(parsedDayNumber) || parsedDayNumber < 1) {
      errs.dayNumber = "Day number must be 1 or greater";
    }

    if (title.trim().length > 100) {
      errs.title = "Title cannot exceed 100 characters";
    }

    if (date.trim()) {
      const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
      if (!dateRegex.test(date.trim())) {
        errs.date = "Format must be YYYY-MM-DD";
      }
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setServerError(null);

    const payload: ItineraryDayCreateRequest = {
      day_number: parseInt(dayNumber.trim(), 10),
      title: title.trim() || null,
      date: date.trim() || null,
    };

    try {
      await onSubmit(payload);
      onClose();
    } catch (err: any) {
      setServerError(err?.message || "Failed to save itinerary day");
    }
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        className="flex-1 justify-end bg-black/60"
      >
        <View className="bg-slate-900 rounded-t-3xl border-t border-slate-800 max-h-[85%] flex flex-col">
          {/* Header */}
          <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-800">
            <Text className="text-lg font-bold text-white">
              {isEditing ? `Edit Day ${initialDay?.day_number}` : "Add Itinerary Day"}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={18} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Form Scroll Content */}
          <ScrollView
            className="px-6 py-4"
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {serverError && (
              <View className="mb-4 p-3 bg-rose-950/40 border border-rose-800 rounded-xl flex-row items-center">
                <AlertCircle size={18} color="#f43f5e" />
                <Text className="text-rose-400 text-sm ml-2 flex-1">
                  {serverError}
                </Text>
              </View>
            )}

            {/* Day Number */}
            <Input
              label="Day Number *"
              placeholder="1"
              keyboardType="number-pad"
              value={dayNumber}
              onChangeText={setDayNumber}
              error={errors.dayNumber}
              helperText="Sequential day index (Day 1, Day 2, etc.)"
            />

            {/* Day Title */}
            <Input
              label="Day Title (Optional)"
              placeholder="e.g. Arrival & Historic Quarter"
              value={title}
              onChangeText={setTitle}
              error={errors.title}
            />

            {/* Date */}
            <Input
              label="Calendar Date (Optional)"
              placeholder="YYYY-MM-DD (e.g. 2026-10-15)"
              value={date}
              onChangeText={setDate}
              error={errors.date}
              helperText="Specific calendar date for this day"
            />

            <View className="h-4" />
          </ScrollView>

          {/* Footer Actions */}
          <View className="p-4 px-6 border-t border-slate-800 flex-row space-x-3">
            <Button
              label="Cancel"
              variant="secondary"
              className="flex-1 mr-2"
              onPress={onClose}
              disabled={isSubmitting}
            />
            <Button
              label={isEditing ? "Save Changes" : "Add Day"}
              className="flex-1 ml-2"
              onPress={handleSave}
              isLoading={isSubmitting}
            />
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};
