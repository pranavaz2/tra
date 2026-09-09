import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TextInputProps,
  TouchableOpacity,
} from "react-native";
import { Eye, EyeOff } from "lucide-react-native";
import clsx from "clsx";

export interface InputProps extends TextInputProps {
  label?: string;
  error?: string | null;
  helperText?: string;
  containerClassName?: string;
  isPassword?: boolean;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  containerClassName = "",
  isPassword = false,
  className = "",
  ...rest
}) => {
  const [showPassword, setShowPassword] = useState(!isPassword);

  return (
    <View className={clsx("w-full mb-4", containerClassName)}>
      {label && (
        <Text className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
          {label}
        </Text>
      )}

      <View className="relative flex-row items-center">
        <TextInput
          className={clsx(
            "w-full bg-slate-900 border text-slate-100 rounded-xl px-4 py-3.5 text-base",
            error
              ? "border-rose-500 focus:border-rose-400"
              : "border-slate-800 focus:border-brand-500",
            isPassword && "pr-12",
            className
          )}
          placeholderTextColor="#64748b"
          secureTextEntry={isPassword && !showPassword}
          autoCapitalize="none"
          {...rest}
        />

        {isPassword && (
          <TouchableOpacity
            className="absolute right-3 p-1.5"
            onPress={() => setShowPassword((prev) => !prev)}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
          >
            {showPassword ? (
              <EyeOff size={20} color="#94a3b8" />
            ) : (
              <Eye size={20} color="#94a3b8" />
            )}
          </TouchableOpacity>
        )}
      </View>

      {error ? (
        <Text className="text-rose-400 text-xs mt-1.5 font-medium">{error}</Text>
      ) : helperText ? (
        <Text className="text-slate-500 text-xs mt-1.5">{helperText}</Text>
      ) : null}
    </View>
  );
};
