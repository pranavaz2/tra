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
import { X, Compass, Car, Bed, Utensils, AlertCircle } from "lucide-react-native";
import {
  ItineraryItemCreateRequest,
  ItineraryItemResponse,
  ItineraryItemType,
  ItineraryDayResponse,
} from "@/core/api/types";
import { Input } from "@/shared/components/ui/Input";
import { Button } from "@/shared/components/ui/Button";
import clsx from "clsx";

interface ItemFormModalProps {
  visible: boolean;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
  initialItem?: ItineraryItemResponse | null;
  dayId: string;
  days?: ItineraryDayResponse[];
  isSubmitting?: boolean;
}

const ITEM_TYPES: { type: ItineraryItemType; label: string; icon: any }[] = [
  { type: "activity", label: "Activity", icon: Compass },
  { type: "transport", label: "Transport", icon: Car },
  { type: "lodging", label: "Lodging", icon: Bed },
  { type: "restaurant", label: "Restaurant", icon: Utensils },
];

export const ItemFormModal: React.FC<ItemFormModalProps> = ({
  visible,
  onClose,
  onSubmit,
  initialItem,
  dayId,
  days = [],
  isSubmitting = false,
}) => {
  const isEditing = !!initialItem;

  const [title, setTitle] = useState("");
  const [itemType, setItemType] = useState<ItineraryItemType>("activity");
  const [description, setDescription] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [cost, setCost] = useState("");
  const [currency, setCurrency] = useState("");
  const [selectedDayId, setSelectedDayId] = useState(dayId);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (visible) {
      if (initialItem) {
        setTitle(initialItem.title || "");
        setItemType(initialItem.item_type || "activity");
        setDescription(initialItem.description || "");
        setStartTime(
          initialItem.start_time ? initialItem.start_time.slice(0, 5) : ""
        );
        setEndTime(
          initialItem.end_time ? initialItem.end_time.slice(0, 5) : ""
        );
        setCost(
          initialItem.cost !== null && initialItem.cost !== undefined
            ? String(initialItem.cost)
            : ""
        );
        setCurrency(initialItem.currency || "");
        setSelectedDayId(initialItem.day_id || dayId);
      } else {
        setTitle("");
        setItemType("activity");
        setDescription("");
        setStartTime("");
        setEndTime("");
        setCost("");
        setCurrency("");
        setSelectedDayId(dayId);
      }
      setErrors({});
      setServerError(null);
    }
  }, [visible, initialItem, dayId]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!title.trim()) {
      errs.title = "Title is required";
    } else if (title.trim().length > 100) {
      errs.title = "Title cannot exceed 100 characters";
    }

    const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)(:([0-5]\d))?$/;
    if (startTime.trim() && !timeRegex.test(startTime.trim())) {
      errs.startTime = "Use HH:MM format (e.g. 09:30)";
    }
    if (endTime.trim() && !timeRegex.test(endTime.trim())) {
      errs.endTime = "Use HH:MM format (e.g. 14:00)";
    }

    if (cost.trim()) {
      const num = Number(cost.trim());
      if (isNaN(num) || num < 0) {
        errs.cost = "Cost must be a positive number";
      }
    }

    if (currency.trim() && currency.trim().length !== 3) {
      errs.currency = "Must be 3 letters (e.g. USD)";
    }

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    setServerError(null);

    const formattedStartTime = startTime.trim()
      ? startTime.trim().length === 5
        ? `${startTime.trim()}:00`
        : startTime.trim()
      : null;

    const formattedEndTime = endTime.trim()
      ? endTime.trim().length === 5
        ? `${endTime.trim()}:00`
        : endTime.trim()
      : null;

    const payload: any = {
      title: title.trim(),
      item_type: itemType,
      description: description.trim() || null,
      start_time: formattedStartTime,
      end_time: formattedEndTime,
      cost: cost.trim() ? parseFloat(cost.trim()) : null,
      currency: currency.trim().toUpperCase() || null,
    };

    if (isEditing) {
      if (selectedDayId && selectedDayId !== initialItem?.day_id) {
        payload.day_id = selectedDayId;
      }
    } else {
      payload.day_id = selectedDayId || dayId;
    }

    try {
      await onSubmit(payload);
      onClose();
    } catch (err: any) {
      setServerError(err?.message || "Failed to save itinerary item");
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
        <View className="bg-slate-900 rounded-t-3xl border-t border-slate-800 max-h-[90%] flex flex-col">
          {/* Header */}
          <View className="flex-row items-center justify-between px-6 py-4 border-b border-slate-800">
            <Text className="text-lg font-bold text-white">
              {isEditing ? "Edit Item" : "Add Itinerary Item"}
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

            {/* Type Selector */}
            <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Item Category
            </Text>
            <View className="flex-row flex-wrap gap-2 mb-4">
              {ITEM_TYPES.map(({ type, label, icon: Icon }) => {
                const isSelected = itemType === type;
                return (
                  <TouchableOpacity
                    key={type}
                    onPress={() => setItemType(type)}
                    className={clsx(
                      "flex-row items-center px-3.5 py-2 rounded-xl border",
                      isSelected
                        ? "bg-brand-600/20 border-brand-500"
                        : "bg-slate-950 border-slate-800"
                    )}
                  >
                    <Icon
                      size={15}
                      color={isSelected ? "#818cf8" : "#94a3b8"}
                    />
                    <Text
                      className={clsx(
                        "text-xs font-semibold ml-1.5",
                        isSelected ? "text-brand-300" : "text-slate-400"
                      )}
                    >
                      {label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Title */}
            <Input
              label="Title *"
              placeholder="e.g. Visit Eiffel Tower"
              value={title}
              onChangeText={setTitle}
              error={errors.title}
              autoFocus={!isEditing}
            />

            {/* Day Selector (if editing and multiple days available) */}
            {isEditing && days.length > 1 && (
              <View className="mb-4">
                <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  Move to Day
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row">
                  {days.map((d) => {
                    const isSelected = selectedDayId === d.day_id;
                    return (
                      <TouchableOpacity
                        key={d.day_id}
                        onPress={() => setSelectedDayId(d.day_id)}
                        className={clsx(
                          "px-3 py-1.5 rounded-lg mr-2 border",
                          isSelected
                            ? "bg-brand-600 border-brand-500"
                            : "bg-slate-800 border-slate-700"
                        )}
                      >
                        <Text
                          className={clsx(
                            "text-xs font-medium",
                            isSelected ? "text-white font-bold" : "text-slate-300"
                          )}
                        >
                          Day {d.day_number}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </View>
            )}

            {/* Time row */}
            <View className="flex-row space-x-3">
              <View className="flex-1 mr-2">
                <Input
                  label="Start Time"
                  placeholder="09:00"
                  value={startTime}
                  onChangeText={setStartTime}
                  error={errors.startTime}
                  helperText="HH:MM format"
                />
              </View>
              <View className="flex-1 ml-2">
                <Input
                  label="End Time"
                  placeholder="11:30"
                  value={endTime}
                  onChangeText={setEndTime}
                  error={errors.endTime}
                  helperText="HH:MM format"
                />
              </View>
            </View>

            {/* Cost and Currency */}
            <View className="flex-row space-x-3">
              <View className="flex-[2] mr-2">
                <Input
                  label="Cost"
                  placeholder="0.00"
                  keyboardType="decimal-pad"
                  value={cost}
                  onChangeText={setCost}
                  error={errors.cost}
                />
              </View>
              <View className="flex-1 ml-2">
                <Input
                  label="Currency"
                  placeholder="USD"
                  autoCapitalize="characters"
                  maxLength={3}
                  value={currency}
                  onChangeText={setCurrency}
                  error={errors.currency}
                />
              </View>
            </View>

            {/* Description / Notes */}
            <Input
              label="Description / Notes"
              placeholder="Add details, booking links, or notes..."
              value={description}
              onChangeText={setDescription}
              multiline
              numberOfLines={3}
              textAlignVertical="top"
              className="h-20 py-2.5"
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
              label={isEditing ? "Save Changes" : "Add Item"}
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
