import React from "react";
import { View, Text, TouchableOpacity } from "react-native";
import { AlertCircle, RefreshCw } from "lucide-react-native";

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  onRetry,
  className = "",
}) => {
  return (
    <View
      className={`bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 flex-row items-center justify-between ${className}`}
    >
      <View className="flex-row items-center flex-1 mr-3">
        <AlertCircle size={20} color="#f43f5e" className="mr-3" />
        <Text className="text-rose-200 text-sm font-medium flex-1 ml-2.5">
          {message}
        </Text>
      </View>

      {onRetry && (
        <TouchableOpacity
          onPress={onRetry}
          className="bg-rose-900/60 px-3 py-1.5 rounded-lg flex-row items-center active:bg-rose-800"
        >
          <RefreshCw size={14} color="#fecdd3" />
          <Text className="text-rose-200 text-xs font-semibold ml-1.5">Retry</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};
