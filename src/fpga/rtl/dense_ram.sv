// Explicit 7-series TDP primitives; one synchronous read and one write port.
// TDP supports NO_CHANGE. RAMB18 SDP x36 does NOT support NO_CHANGE in UNISIM.
// Byte pools: 2048x9 (8 data bits). Wider pools: parallel 1024x18 (16 data
// bits each). This costs 60 RAMB18 for the core instead of the 52 SDP estimate.
// Capacities/latency/byte semantics are unchanged. No memory-wide reset.
module dense_ram #(parameter WIDTH=8, DEPTH=32768, AW=15)(
 input wire clk, input wire we, input wire [AW-1:0] wa,
 input wire [WIDTH-1:0] wd, input wire re, input wire [AW-1:0] ra,
 output wire [WIDTH-1:0] q);
 localparam LANE=(WIDTH==8)?8:16;
 localparam PHYS_WIDTH=(WIDTH==8)?9:18;
 localparam BANK_DEPTH=(WIDTH==8)?2048:1024;
 localparam ROW_BITS=(WIDTH==8)?11:10;
 localparam BANKS=(DEPTH+BANK_DEPTH-1)/BANK_DEPTH;
 localparam LANES=WIDTH/LANE;
 localparam SEL_BITS=(BANKS>1)?$clog2(BANKS):1;
 wire [WIDTH-1:0] bank_q[0:BANKS-1];
 reg [SEL_BITS-1:0] selected;
 wire ren=re && ra<DEPTH && !(we&&wa==ra);
 wire [13:0] read_address=(ra%BANK_DEPTH)<<(14-ROW_BITS);
 wire [13:0] write_address=(wa%BANK_DEPTH)<<(14-ROW_BITS);
 always @(posedge clk)if(ren)selected<=ra/BANK_DEPTH;
 assign q=bank_q[selected];
 genvar b,l;
 generate for(b=0;b<BANKS;b=b+1)begin:bank
  for(l=0;l<LANES;l=l+1)begin:lane
   wire [15:0] rdata;
   wire [15:0] wdata={{(16-LANE){1'b0}},wd[l*LANE+:LANE]};
   RAMB18E1 #(.RAM_MODE("TDP"),.READ_WIDTH_A(PHYS_WIDTH),.WRITE_WIDTH_A(0),
    .READ_WIDTH_B(0),.WRITE_WIDTH_B(PHYS_WIDTH),.DOA_REG(0),.DOB_REG(0),
    .WRITE_MODE_A("NO_CHANGE"),.WRITE_MODE_B("NO_CHANGE"),.SIM_COLLISION_CHECK("ALL")) mem(
    .CLKARDCLK(clk),.CLKBWRCLK(clk),.ENARDEN(ren&&(ra/BANK_DEPTH==b)),
    .ENBWREN(we&&wa<DEPTH&&(wa/BANK_DEPTH==b)),.WEA(2'b00),.WEBWE(4'b1111),
    .ADDRARDADDR(read_address),.ADDRBWRADDR(write_address),
    .DIADI(16'd0),.DIBDI(wdata),.DIPADIP(2'd0),.DIPBDIP(2'd0),
    .DOADO(rdata),.DOBDO(),.DOPADOP(),.DOPBDOP(),
    .REGCEAREGCE(1'b1),.REGCEB(1'b1),.RSTRAMARSTRAM(1'b0),.RSTRAMB(1'b0),
    .RSTREGARSTREG(1'b0),.RSTREGB(1'b0));
   assign bank_q[b][l*LANE+:LANE]=rdata[LANE-1:0];
  end
 end endgenerate
endmodule
