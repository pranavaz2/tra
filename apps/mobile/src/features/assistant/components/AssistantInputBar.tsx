/**
 * AssistantInputBar Component.
 *
 * Text input bar with context-aware prompt suggestion chips and send button.
 */

import React, { useState } from "react";
import {
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Text,
  ActivityIndicator,
} from "react-native";
import { Send, Sparkles } from "lucide-react-native";

interface AssistantInputBarProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  tripTitle?: string;
  /** Number of itinerary days planned — used for context-specific chips. */
  itineraryDaysCount?: number;
  /** Name of the first itinerary stop — used for context-specific chips. */
  firstStopName?: string;
}

export const AssistantInputBar: React.FC<AssistantInputBarProps> = ({
  onSend,
  isLoading = false,
  tripTitle,
  itineraryDaysCount = 0,
  firstStopName,
}) => {
  const [text, setText] = useState<string>("");

  const cityName = tripTitle ? tripTitle.split(",")[0].trim() : "";

  const quickPrompts = React.useMemo(() => {
    // If we have real itinerary data, build highly specific chips
    if (itineraryDaysCount > 0) {
      const chips = [
        `Is the Day 1 timing realistic?`,
        itineraryDaysCount > 1 ? `Is Day ${itineraryDaysCount} too busy?` : `Check schedule pacing`,
        firstStopName
          ? `Suggest a restaurant near ${firstStopName}`
          : `Suggest restaurants near Day 1 stops`,
        `What's the budget remaining?`,
        `Check for schedule conflicts`,
        cityName ? `Hidden gems in ${cityName}` : `Any hidden gems nearby?`,
      ];
      return chips;
    }
    // Generic fallback when no itinerary exists yet
    if (!cityName) {
      return [
        "Check schedule conflicts",
        "Estimate travel time",
        "Check budget risks",
        "Find top-rated dinner spots",
        "What is my budget status?",
      ];
    }
    return [
      `Check schedule conflicts`,
      `Estimate travel times in ${cityName}`,
      `Famous local food to try in ${cityName}`,
      `Check budget & spending pace`,
      `Best sights & hidden gems in ${cityName}`,
      `What should I pack for ${cityName}?`,
    ];
  }, [cityName, itineraryDaysCount, firstStopName]);


  const handleSend = () => {
    if (!text.trim() || isLoading) return;
    onSend(text.trim());
    setText("");
  };

  const handleChipPress = (prompt: string) => {
    if (isLoading) return;
    onSend(prompt);
  };

  return (
    <View className="bg-slate-950 border-t border-slate-900 pb-2">
      {/* Quick Prompt Chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 8 }}
      >
        {quickPrompts.map((prompt, idx) => (
          <TouchableOpacity
            key={idx}
            onPress={() => handleChipPress(prompt)}
            disabled={isLoading}
            className="mr-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 active:bg-slate-800 flex-row items-center"
          >
            <Sparkles size={12} color="#818cf8" />
            <Text className="text-slate-300 text-xs ml-1.5">{prompt}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Input row */}
      <View className="flex-row items-center px-4 pt-1 pb-2">
        <View className="flex-1 flex-row items-center bg-slate-900 border border-slate-800 rounded-2xl px-3.5 py-2 mr-2">
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Ask AI or request a schedule change..."
            placeholderTextColor="#64748b"
            className="flex-1 text-white text-sm"
            multiline
            maxLength={1000}
            editable={!isLoading}
          />
        </View>

        <TouchableOpacity
          onPress={handleSend}
          disabled={!text.trim() || isLoading}
          className={`w-11 h-11 rounded-2xl items-center justify-center ${
            text.trim() && !isLoading
              ? "bg-brand-600 active:bg-brand-500"
              : "bg-slate-900 border border-slate-800 opacity-60"
          }`}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color="#818cf8" />
          ) : (
            <Send
              size={18}
              color={text.trim() ? "#ffffff" : "#64748b"}
            />
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};
