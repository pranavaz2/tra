import React from "react";
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  TouchableOpacityProps,
  View,
} from "react-native";
import clsx from "clsx";

export type ButtonVariant = "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends TouchableOpacityProps {
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: React.ReactNode;
  className?: string;
  labelClassName?: string;
}

export const Button: React.FC<ButtonProps> = ({
  label,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  icon,
  className = "",
  labelClassName = "",
  ...rest
}) => {
  const isDisabled = disabled || isLoading;

  const baseStyles = "flex-row items-center justify-center rounded-xl font-semibold";

  const sizeStyles = {
    sm: "px-3 py-2",
    md: "px-5 py-3.5",
    lg: "px-6 py-4",
  }[size];

  const variantStyles = {
    primary: "bg-brand-600 active:bg-brand-700",
    secondary: "bg-slate-800 active:bg-slate-700",
    outline: "bg-transparent border border-slate-300 dark:border-slate-700 active:bg-slate-100 dark:active:bg-slate-800",
    ghost: "bg-transparent active:bg-slate-100 dark:active:bg-slate-800",
    danger: "bg-rose-600 active:bg-rose-700",
  }[variant];

  const labelSizeStyles = {
    sm: "text-xs font-medium",
    md: "text-sm font-semibold",
    lg: "text-base font-semibold",
  }[size];

  const labelVariantStyles = {
    primary: "text-white",
    secondary: "text-white",
    outline: "text-slate-800 dark:text-slate-200",
    ghost: "text-slate-700 dark:text-slate-300",
    danger: "text-white",
  }[variant];

  return (
    <TouchableOpacity
      className={clsx(
        baseStyles,
        sizeStyles,
        variantStyles,
        isDisabled && "opacity-50",
        className
      )}
      disabled={isDisabled}
      activeOpacity={0.7}
      {...rest}
    >
      {isLoading ? (
        <ActivityIndicator
          size="small"
          color={variant === "outline" || variant === "ghost" ? "#6366f1" : "#ffffff"}
        />
      ) : (
        <View className="flex-row items-center justify-center space-x-2">
          {icon && <View className="mr-2">{icon}</View>}
          <Text className={clsx(labelSizeStyles, labelVariantStyles, labelClassName)}>
            {label}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
};
