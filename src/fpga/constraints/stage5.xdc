# V2.1 schematic UART p10, clock/reset p6-7. FPGA RX U5, TX T6.
create_clock -period 20.000 -name sys_clk [get_ports sys_clk]
set_property -dict {PACKAGE_PIN R4 IOSTANDARD LVCMOS33} [get_ports sys_clk]
set_property -dict {PACKAGE_PIN U2 IOSTANDARD LVCMOS33} [get_ports sys_rst_n]
set_property -dict {PACKAGE_PIN U5 IOSTANDARD LVCMOS33} [get_ports uart_rx]
set_property -dict {PACKAGE_PIN T6 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} [get_ports uart_tx]
# Raw asynchronous reset only to parallel two-stage release synchronizers.
set_false_path -from [get_ports sys_rst_n] -to [get_pins -hier -filter {NAME =~ *reset_sync_reg*/CLR}]
# The byte bridge has its own two-stage reset release chain named sync.
# Cover only its asynchronous clear pins; its clocked release path stays timed.
set_false_path -from [get_ports sys_rst_n] -to [get_pins -hier -filter {NAME =~ system/sync_reg*/CLR}]
# Async UART input is timed from the synchronizer second stage onwards.
set_false_path -from [get_ports uart_rx] -to [get_pins -hier -filter {NAME =~ *rx_sync_reg[0]/D}]
# UART TX is sampled by an independent baud clock, not a synchronous board bus.
set_false_path -to [get_ports uart_tx]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
