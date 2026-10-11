import type { ComponentType } from "react";
import {
  Bot,
  CalendarDays,
  ClipboardList,
  House,
  LayoutDashboard,
  MessageCircle,
  UserRound,
} from "lucide-react-native";

type TabIconProps = {
  color: string;
  size: number;
};

type IconComponent = ComponentType<TabIconProps>;

function renderTabIcon(Icon: IconComponent) {
  return function TabIcon({ color, size }: TabIconProps) {
    return <Icon color={color} size={size} />;
  };
}

export const tabIcons = {
  home: renderTabIcon(House),
  chats: renderTabIcon(MessageCircle),
  aiChat: renderTabIcon(Bot),
  bookings: renderTabIcon(ClipboardList),
  schedule: renderTabIcon(CalendarDays),
  admin: renderTabIcon(LayoutDashboard),
  account: renderTabIcon(UserRound),
};
