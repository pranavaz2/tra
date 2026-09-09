import React from "react";
import { View, ViewProps } from "react-native";
import clsx from "clsx";

export interface CardProps extends ViewProps {
  className?: string;
}

export const Card: React.FC<CardProps> = ({ children, className = "", ...rest }) => {
  return (
    <View
      className={clsx(
        "bg-slate-900 border border-slate-800/80 rounded-2xl p-5 shadow-sm",
        className
      )}
      {...rest}
    >
      {children}
    </View>
  );
};
