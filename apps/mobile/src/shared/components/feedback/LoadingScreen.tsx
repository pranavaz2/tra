import React from "react";
import { View, Text, ActivityIndicator } from "react-native";

export const LoadingScreen: React.FC<{ message?: string }> = ({
  message = "Loading Travix...",
}) => {
  return (
    <View className="flex-1 bg-slate-950 items-center justify-center p-6">
      <View className="w-16 h-16 rounded-2xl bg-brand-600/20 border border-brand-500/30 items-center justify-center mb-6">
        <ActivityIndicator size="large" color="#6366f1" />
      </View>
      <Text className="text-white text-lg font-semibold tracking-wide">{message}</Text>
      <Text className="text-slate-500 text-sm mt-2">Preparing your journeys</Text>
    </View>
  );
};
