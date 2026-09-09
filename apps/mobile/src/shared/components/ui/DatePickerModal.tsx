import React, { useState } from "react";
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ScrollView,
} from "react-native";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, X, Check } from "lucide-react-native";
import { Button } from "./Button";
import clsx from "clsx";

interface DatePickerModalProps {
  visible: boolean;
  onClose: () => void;
  departureDate: string; // YYYY-MM-DD or ""
  returnDate: string; // YYYY-MM-DD or ""
  onSelectDates: (departure: string, returnDate: string) => void;
}

const DAYS_OF_WEEK = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function formatIsoDate(year: number, month: number, day: number): string {
  const m = String(month + 1).padStart(2, "0");
  const d = String(day).padStart(2, "0");
  return `${year}-${m}-${d}`;
}

export const DatePickerModal: React.FC<DatePickerModalProps> = ({
  visible,
  onClose,
  departureDate,
  returnDate,
  onSelectDates,
}) => {
  const today = new Date();
  const [currentYear, setCurrentYear] = useState(today.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(today.getMonth()); // 0-indexed
  const [activeTarget, setActiveTarget] = useState<"departure" | "return">("departure");

  const [tempDeparture, setTempDeparture] = useState(departureDate);
  const [tempReturn, setTempReturn] = useState(returnDate);

  // Sync state when opening modal
  React.useEffect(() => {
    setTempDeparture(departureDate);
    setTempReturn(returnDate);
    if (departureDate) {
      const [y, m] = departureDate.split("-").map(Number);
      if (y && m) {
        setCurrentYear(y);
        setCurrentMonth(m - 1);
      }
    }
  }, [visible, departureDate, returnDate]);

  const nextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonth((m) => m + 1);
    }
  };

  const prevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonth((m) => m - 1);
    }
  };

  // Calendar calculations
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
  const firstDayOfWeek = new Date(currentYear, currentMonth, 1).getDay();

  const handleSelectDay = (day: number) => {
    const selectedIso = formatIsoDate(currentYear, currentMonth, day);

    if (activeTarget === "departure") {
      setTempDeparture(selectedIso);
      // If return date exists and is before new departure, reset return date
      if (tempReturn && tempReturn < selectedIso) {
        setTempReturn("");
      }
      // Auto-switch to picking return date
      setActiveTarget("return");
    } else {
      // Picking return date: must be >= departure
      if (tempDeparture && selectedIso < tempDeparture) {
        // If user tapped earlier date, treat it as new departure
        setTempDeparture(selectedIso);
      } else {
        setTempReturn(selectedIso);
      }
    }
  };

  const handleApplyPreset = (daysFromNow: number, tripLengthDays: number) => {
    const start = new Date();
    start.setDate(start.getDate() + daysFromNow);
    const end = new Date(start);
    end.setDate(end.getDate() + tripLengthDays);

    const startIso = formatIsoDate(start.getFullYear(), start.getMonth(), start.getDate());
    const endIso = formatIsoDate(end.getFullYear(), end.getMonth(), end.getDate());

    setTempDeparture(startIso);
    setTempReturn(endIso);
  };

  const handleSave = () => {
    onSelectDates(tempDeparture, tempReturn);
    onClose();
  };

  const handleClear = () => {
    setTempDeparture("");
    setTempReturn("");
    onSelectDates("", "");
    onClose();
  };

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1 justify-end bg-black/60">
        <View className="bg-slate-900 border-t border-slate-800 rounded-t-3xl p-6 max-h-[90%]">
          {/* Header */}
          <View className="flex-row items-center justify-between pb-4 border-b border-slate-800">
            <View className="flex-row items-center">
              <CalendarIcon size={20} color="#818cf8" />
              <Text className="text-white text-lg font-bold ml-2.5">Select Travel Dates</Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              className="w-8 h-8 rounded-full bg-slate-800 items-center justify-center"
            >
              <X size={16} color="#94a3b8" />
            </TouchableOpacity>
          </View>

          {/* Quick Target Tabs */}
          <View className="flex-row space-x-3 my-4">
            <TouchableOpacity
              onPress={() => setActiveTarget("departure")}
              className={clsx(
                "flex-1 p-3 rounded-xl border mr-2",
                activeTarget === "departure"
                  ? "bg-brand-600/20 border-brand-500"
                  : "bg-slate-800/60 border-slate-800"
              )}
            >
              <Text className="text-slate-400 text-xs font-semibold uppercase">Departure</Text>
              <Text className="text-white text-sm font-bold mt-0.5">
                {tempDeparture || "Select date"}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => setActiveTarget("return")}
              className={clsx(
                "flex-1 p-3 rounded-xl border ml-2",
                activeTarget === "return"
                  ? "bg-brand-600/20 border-brand-500"
                  : "bg-slate-800/60 border-slate-800"
              )}
            >
              <Text className="text-slate-400 text-xs font-semibold uppercase">Return</Text>
              <Text className="text-white text-sm font-bold mt-0.5">
                {tempReturn || "Select date"}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Quick Presets */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mb-4">
            <View className="flex-row space-x-2">
              <TouchableOpacity
                onPress={() => handleApplyPreset(3, 4)}
                className="bg-slate-800 border border-slate-700/60 px-3 py-1.5 rounded-lg mr-2"
              >
                <Text className="text-slate-300 text-xs font-medium">This Weekend</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => handleApplyPreset(14, 7)}
                className="bg-slate-800 border border-slate-700/60 px-3 py-1.5 rounded-lg mr-2"
              >
                <Text className="text-slate-300 text-xs font-medium">In 2 Weeks (7d)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={() => handleApplyPreset(30, 10)}
                className="bg-slate-800 border border-slate-700/60 px-3 py-1.5 rounded-lg mr-2"
              >
                <Text className="text-slate-300 text-xs font-medium">Next Month (10d)</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>

          {/* Month Navigation */}
          <View className="flex-row items-center justify-between py-2 mb-2">
            <TouchableOpacity onPress={prevMonth} className="p-2">
              <ChevronLeft size={22} color="#cbd5e1" />
            </TouchableOpacity>
            <Text className="text-white text-base font-bold">
              {monthNames[currentMonth]} {currentYear}
            </Text>
            <TouchableOpacity onPress={nextMonth} className="p-2">
              <ChevronRight size={22} color="#cbd5e1" />
            </TouchableOpacity>
          </View>

          {/* Days of Week Header */}
          <View className="flex-row justify-between mb-2 px-1">
            {DAYS_OF_WEEK.map((d) => (
              <Text key={d} className="text-slate-500 text-xs font-semibold w-9 text-center">
                {d}
              </Text>
            ))}
          </View>

          {/* Days Grid */}
          <View className="flex-row flex-wrap mb-6">
            {/* Empty slots before first day */}
            {Array.from({ length: firstDayOfWeek }).map((_, i) => (
              <View key={`empty-${i}`} className="w-[14.28%] h-10" />
            ))}

            {/* Month days */}
            {Array.from({ length: daysInMonth }).map((_, idx) => {
              const day = idx + 1;
              const iso = formatIsoDate(currentYear, currentMonth, day);
              const isDeparture = tempDeparture === iso;
              const isReturn = tempReturn === iso;
              const isInRange =
                tempDeparture && tempReturn && iso > tempDeparture && iso < tempReturn;

              return (
                <TouchableOpacity
                  key={iso}
                  onPress={() => handleSelectDay(day)}
                  className={clsx(
                    "w-[14.28%] h-10 items-center justify-center rounded-xl",
                    isDeparture && "bg-brand-600 rounded-r-none",
                    isReturn && "bg-brand-600 rounded-l-none",
                    isDeparture && isReturn && "rounded-xl",
                    isInRange && "bg-brand-600/20 rounded-none"
                  )}
                >
                  <Text
                    className={clsx(
                      "text-sm font-semibold",
                      isDeparture || isReturn
                        ? "text-white"
                        : isInRange
                        ? "text-brand-300"
                        : "text-slate-200"
                    )}
                  >
                    {day}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Action Buttons */}
          <View className="flex-row space-x-3 pt-2 border-t border-slate-800">
            <Button
              label="Clear"
              variant="outline"
              size="md"
              className="flex-1 mr-2"
              onPress={handleClear}
            />
            <Button
              label="Save Dates"
              variant="primary"
              size="md"
              className="flex-1 ml-2"
              icon={<Check size={16} color="#ffffff" />}
              onPress={handleSave}
            />
          </View>
        </View>
      </View>
    </Modal>
  );
};
